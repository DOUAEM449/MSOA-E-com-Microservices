
import { orderService } from "./orderService";

const STORAGE_KEY = "msoa-shop-payments";

function loadPayments() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) ?? [];
  } catch {
    return [];
  }
}

let payments = loadPayments();

function savePayments() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payments));
}

export const paymentService = {
  // GET /api/payments
  async getPayments() {
    return [...payments];
  },

  // GET /api/payments/order/{orderId}
  async getPaymentByOrder(orderId) {
    return payments.find(
      (payment) => payment.orderId === orderId
    ) ?? null;
  },

  // POST /api/payments
  async processPayment(orderId, method = "CARD") {
    const order = await orderService.getOrderById(orderId);

    if (!order) {
      throw new Error("Order not found.");
    }

    if (order.status !== "PENDING_PAYMENT") {
      throw new Error("Order is not awaiting payment.");
    }

    const existing = await this.getPaymentByOrder(orderId);

    if (existing) {
      throw new Error("Payment already attempted for this order.");
    }

    // Simulated payment: always succeeds for now.
    const payment = {
      id: crypto.randomUUID(),
      orderId,
      amount: order.total,
      method,
      status: "SUCCESS",
      createdAt: new Date().toISOString()
    };

    payments.push(payment);
    savePayments();

    await orderService.updateStatus(orderId, "PAID");

    return payment;
  }
};
