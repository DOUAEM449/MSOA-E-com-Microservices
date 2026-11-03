
import { inventoryService } from "./inventoryService";

const STORAGE_KEY = "msoa-shop-orders";

function loadOrders() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) ?? [];
  } catch {
    return [];
  }
}

let orders = loadOrders();

function saveOrders() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(orders));
}

export const orderService = {
  // GET /api/orders
  async getOrders(userId) {
    if (!userId) {
      throw new Error("Authentication required.");
    }

    return orders.filter((order) => order.userId === userId);
  },

  // GET /api/orders/{id}
  async getOrderById(id) {
    return orders.find((order) => order.id === id) ?? null;
  },

  // POST /api/orders
  async createOrder(items, customer, userId) {
    if (!userId) {
      throw new Error("Authentication required.");
    }

    // Keep the existing implementation...
    if (!items.length) {
      throw new Error("Cannot create an empty order.");
    }

    const reservationItems = items.map((item) => ({
      productId: item.id,
      quantity: item.quantity
    }));

    // Verify and reserve stock through Inventory.
    await inventoryService.reserve(reservationItems);

    const order = {
      id: crypto.randomUUID(),
      userId,
      customer,
      items: items.map((item) => ({
        productId: item.id,
        name: item.name,
        price: item.price,
        quantity: item.quantity
      })),
      total: items.reduce(
        (sum, item) => sum + item.price * item.quantity,
        0
      ),
      status: "PENDING_PAYMENT",
      createdAt: new Date().toISOString()
    };

    orders.push(order);
    saveOrders();

    return order;
  },

  // PATCH /api/orders/{id}/status
  async updateStatus(id, status) {
    const order = orders.find((order) => order.id === id);

    if (!order) {
      throw new Error("Order not found.");
    }

    const allowedTransitions = {
      PENDING_PAYMENT: ["PAID", "CANCELLED"],
      PAID: ["SHIPPED", "CANCELLED"],
      SHIPPED: ["DELIVERED"],
      DELIVERED: [],
      CANCELLED: []
    };

    if (!allowedTransitions[order.status]?.includes(status)) {
      throw new Error(
        `Invalid transition: ${order.status} → ${status}`
      );
    }

    order.status = status;
    saveOrders();

    return order;
  },

  // POST /api/orders/{id}/cancel
  async cancelOrder(id) {
    const order = orders.find((order) => order.id === id);

    if (!order) {
      throw new Error("Order not found.");
    }

    if (!["PENDING_PAYMENT", "PAID"].includes(order.status)) {
      throw new Error("This order cannot be cancelled.");
    }

    await inventoryService.release(
      order.items.map((item) => ({
        productId: item.productId,
        quantity: item.quantity
      }))
    );

    order.status = "CANCELLED";
    saveOrders();

    return order;
  }
};
