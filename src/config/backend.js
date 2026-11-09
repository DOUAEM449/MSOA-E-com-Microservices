
const BACKEND_MODE = {
  AUTH: "rest",
  CATALOG: "rest",
  INVENTORY: "mock",
  ORDERS: "rest",
  PAYMENTS: "mock",
  SHIPPING: "mock",
};

const API_URLS = {
  AUTH: "http://localhost:8081",
  CATALOG: "http://localhost:8082",
  INVENTORY: "http://localhost:8083",
  ORDERS: "http://localhost:8084",
  PAYMENTS: "http://localhost:8085",
  SHIPPING: "http://localhost:8086",
};

export { BACKEND_MODE, API_URLS };
