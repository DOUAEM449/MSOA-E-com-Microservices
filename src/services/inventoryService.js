
import { products } from "../data/products";

const STORAGE_KEY = "msoa-shop-inventory";

// Initialize inventory from the hardcoded product table.
function loadInventory() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);

    if (saved) {
      return JSON.parse(saved);
    }
  } catch {
    // Fall back to initial stock.
  }

  return Object.fromEntries(
    products.map((product) => [product.id, product.stock])
  );
}

let inventory = loadInventory();

function saveInventory() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(inventory));
}

export const inventoryService = {
  // GET /api/inventory/{productId}
  async getStock(productId) {
    return inventory[productId] ?? 0;
  },

  // POST /api/inventory/check
  async checkAvailability(items) {
    return items.every(
      (item) =>
        item.quantity > 0 &&
        (inventory[item.productId] ?? 0) >= item.quantity
    );
  },

  // POST /api/inventory/reserve
  async reserve(items) {
    const available = await this.checkAvailability(items);

    if (!available) {
      throw new Error("Insufficient stock for one or more products.");
    }

    // All items are checked before modifying inventory.
    for (const item of items) {
      inventory[item.productId] -= item.quantity;
    }

    saveInventory();

    return {
      success: true,
      message: "Stock reserved successfully."
    };
  },

  // POST /api/inventory/release
  async release(items) {
    for (const item of items) {
      if (!(item.productId in inventory)) {
        throw new Error(`Unknown product: ${item.productId}`);
      }
    }

    for (const item of items) {
      inventory[item.productId] += item.quantity;
    }

    saveInventory();

    return {
      success: true,
      message: "Stock released successfully."
    };
  }
};
