# MSOA — SQLite starter databases

Six independent databases for six independently implemented REST microservices. Each folder contains a ready-to-use `.db` file, `schema.sql`, and `seed.sql`.

## Ownership
- `auth/auth.db`: users
- `catalog/catalog.db`: products
- `inventory/inventory.db`: stock
- `orders/orders.db`: orders and order_items
- `payments/payments.db`: payments
- `shipping/shipping.db`: shipments

**Important:** Services communicate through REST, not by querying each other's database. IDs such as `product_id`, `user_id`, and `order_id` are references across service boundaries; they deliberately have no cross-database foreign keys.

## Setup
SQLite is embedded; no server required. To rebuild any database using the SQLite CLI:

```sh
cd catalog
sqlite3 catalog.db < schema.sql
sqlite3 catalog.db < seed.sql
```

Run those commands on a **new or empty database file**. The supplied `.db` files are already populated; do not re-run seed scripts on them.

## REST JSON mapping
- Catalog: `products` fields `id,name,category,price,image,description`.
- Inventory: `stock.product_id` -> API `productId`; `stock.quantity` -> API `stock`.
- Orders: `orders` + `order_items` -> API order object with `customer:{name,address,city}`, `items:[{productId,name,price,quantity}]`, `total`, `status`, `createdAt`.
- Payments: payment object with `id,orderId,amount,method,status,createdAt`.
- Shipping: shipment object with `id,orderId,address:{name,address,city},trackingNumber,status,createdAt,updatedAt`.
- Auth: return `{user:{id,name,email,role},token}` from login. **The supplied placeholder is NOT a password hash**; implement secure hashing and create your own test credentials before enabling real authentication.

## Important compatibility notes
The six catalog products and prices are illustrative. **Before integrating with the supplied React frontend, synchronize catalog rows and inventory quantities with `src/data/products.js`** (the existing frontend mock catalog), including images if needed. This avoids inconsistent prices and product identities between mock and REST modes.

The seeded delivered order is a historical sample and **does not deduct stock** from the current inventory snapshot. For new orders, Orders must coordinate atomic stock reservation via Inventory; on cancellation, coordinate release. Payments and Shipping must coordinate status updates with Orders. These cross-service workflows are not implemented by SQLite files alone.

SQLite SQL syntax is broadly portable, but adapting these scripts for MySQL/PostgreSQL/SQL Server may require changes to types, auto-increment syntax, and constraints.

CORS, JWT validation, route implementation, and concurrency control belong in each backend; these files provide data storage only.
