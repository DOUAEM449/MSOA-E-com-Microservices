import { products } from "../data/products";
import { BACKEND_MODE, API_URLS } from "../config/backend";

export const catalogService = {
  async getProducts() {
    if (BACKEND_MODE.CATALOG === "mock") {
      return products;
    }

    const response = await fetch(`${API_URLS.CATALOG}/products`);

    if (!response.ok) {
      throw new Error("Failed to load products");
    }

    return response.json();
  },

  async getProductById(id) {
    if (BACKEND_MODE.CATALOG === "mock") {
      return products.find(
        (product) => String(product.id) === String(id)
      ) ?? null;
    }

    const response = await fetch(
      `${API_URLS.CATALOG}/products/${encodeURIComponent(id)}`
    );

    if (response.status === 404) {
      return null;
    }

    if (!response.ok) {
      throw new Error("Failed to load product");
    }

    return response.json();
  }
};
