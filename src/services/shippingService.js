
const STORAGE_KEY = "msoa-shop-shipments";

function loadShipments() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) ?? [];
  } catch {
    return [];
  }
}

function saveShipments(shipments) {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify(shipments)
  );
}

export const shippingService = {
  // GET /api/shipments
  async getShipments() {
    return loadShipments();
  },

  // GET /api/shipments/order/{orderId}
  async getShipmentByOrder(orderId) {
    return loadShipments().find(
      (shipment) => shipment.orderId === orderId
    ) ?? null;
  },

  // POST /api/shipments
  async createShipment(orderId, address) {
    const shipments = loadShipments();

    if (shipments.some((s) => s.orderId === orderId)) {
      throw new Error("Shipment already exists for this order.");
    }

    const shipment = {
      id: crypto.randomUUID(),
      orderId,
      address,
      trackingNumber: `MSOA-${crypto.randomUUID()
        .slice(0, 8)
        .toUpperCase()}`,
      status: "PREPARING",
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };

    shipments.push(shipment);
    saveShipments(shipments);

    return shipment;
  },

  // PATCH /api/shipments/{id}/status
  async updateStatus(id, status) {
    const shipments = loadShipments();

    const shipment = shipments.find(
      (item) => item.id === id
    );

    if (!shipment) {
      throw new Error("Shipment not found.");
    }

    const transitions = {
      PREPARING: ["SHIPPED", "CANCELLED"],
      SHIPPED: ["IN_TRANSIT"],
      IN_TRANSIT: ["DELIVERED"],
      DELIVERED: [],
      CANCELLED: []
    };

    if (!transitions[shipment.status]?.includes(status)) {
      throw new Error(
        `Invalid shipment transition: ${shipment.status} → ${status}`
      );
    }

    shipment.status = status;
    shipment.updatedAt = new Date().toISOString();

    saveShipments(shipments);

    return shipment;
  }
};
