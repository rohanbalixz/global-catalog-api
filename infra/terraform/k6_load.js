import http from 'k6/http';
import { check, sleep } from 'k6';

// Safe env read for older k6 versions
const BASE = (typeof __ENV !== 'undefined' && __ENV.BASE_URL) ? __ENV.BASE_URL : 'http://127.0.0.1:8000';

// Tiny inline uuid (no remote import)
function uuid4() {
  // not cryptographically secure — fine for load ids
  return 'xxxxxxxx'.replace(/x/g, () => (Math.random()*16|0).toString(16));
}

export const options = {
  scenarios: {
    health_read: {
      executor: 'ramping-arrival-rate',
      startRate: 5,
      timeUnit: '1s',
      preAllocatedVUs: 20,
      maxVUs: 80,
      stages: [
        { target: 25, duration: '20s' },
        { target: 50, duration: '20s' },
        { target: 0,  duration: '10s' },
      ],
      exec: 'health',
    },
    product_read_write: {
      executor: 'constant-arrival-rate',
      rate: 8,
      timeUnit: '1s',
      duration: '30s',
      preAllocatedVUs: 20,
      maxVUs: 60,
      exec: 'catalog',
    },
  },
  thresholds: {
    'http_req_failed{scenario:health_read}': ['rate<0.01'],
    'http_req_duration{scenario:health_read}': ['p(95)<250'],
    'http_req_failed{scenario:product_read_write}': ['rate<0.02'],
    'http_req_duration{scenario:product_read_write}': ['p(95)<450'],
  },
};

export function health() {
  const res = http.get(`${BASE}/health`);
  check(res, {
    '200': (r) => r.status === 200,
    'has region header': (r) => !!r.headers['X-Region'],
  });
  sleep(0.05);
}

export function catalog() {
  const pid = 'PX-' + uuid4();
  const body = JSON.stringify({
    product_id: pid,
    region_code: 'us-east-1',
    title: 'k6 item',
    currency: 'USD',
    price: 9.99,
    attrs: { ephemeral: true }
  });
  const put = http.put(`${BASE}/products`, body, { headers: { 'Content-Type': 'application/json' }});
  check(put, { 'put 200': (r) => r.status === 200 });

  const getOne = http.get(`${BASE}/products/${pid}/us-east-1`);
  check(getOne, { 'get 200': (r) => r.status === 200 });

  const inv = JSON.stringify({ product_id: pid, warehouse_id: 'K6', region_code: 'us-east-1', inc: 1, dec: 0 });
  const postInv = http.post(`${BASE}/inventory`, inv, { headers: { 'Content-Type': 'application/json' }});
  check(postInv, { 'inv 200': (r) => r.status === 200 });

  sleep(0.05);
}
