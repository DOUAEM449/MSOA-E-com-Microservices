import { inventoryService } from "../services/inventoryService";
import { useEffect, useState } from "react";
import { useCart } from "../context/CartContext";
import {
  Box,
  Container,
  Typography,
  TextField,
  MenuItem,
  Stack,
  Alert
} from "@mui/material";

import { SearchOutlined } from "@mui/icons-material";
import ProductCard from "../components/ProductCard";
import { products } from "../data/products";

export default function Products() {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("All");
  const { addToCart } = useCart();
  const [availableProducts, setAvailableProducts] = useState([]);

  useEffect(() => {
    async function loadProducts() {
      const data = await Promise.all(
        products.map(async (product) => ({
          ...product,
          stock: await inventoryService.getStock(product.id)
        }))
      );

      setAvailableProducts(data);
    }

    loadProducts();
  }, []);

  const categories = [
    "All",
    ...new Set(availableProducts.map((product) => product.category))
  ];

  const filteredProducts = availableProducts.filter((product) => {
    const matchesSearch = product.name
      .toLowerCase()
      .includes(search.toLowerCase());

    const matchesCategory =
      category === "All" || product.category === category;

    return matchesSearch && matchesCategory;
  });

  const handleAddToCart = (product) => {
    addToCart(product);
  };

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 6 } }}>
      <Stack spacing={3}>
        <Box>
          <Typography
            component="h1"
            variant="h4"
            fontWeight={800}
            sx={{ fontSize: { xs: "1.7rem", md: "2.2rem" } }}
          >
            Product Catalogue
          </Typography>

          <Typography color="text.secondary" sx={{ mt: 1 }}>
            Browse our collection of products.
          </Typography>
        </Box>

        <Stack
          direction={{ xs: "column", sm: "row" }}
          spacing={2}
        >
          <TextField
            fullWidth
            label="Search products"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            slotProps={{
              input: {
                startAdornment: (
                  <SearchOutlined sx={{ mr: 1, color: "text.secondary" }} />
                )
              }
            }}
          />

          <TextField
            select
            label="Category"
            value={category}
            onChange={(event) => setCategory(event.target.value)}
            sx={{ minWidth: { sm: 200 } }}
          >
            {categories.map((item) => (
              <MenuItem key={item} value={item}>
                {item}
              </MenuItem>
            ))}
          </TextField>
        </Stack>

        {filteredProducts.length === 0 ? (
          <Alert severity="info">
            No products match your search.
          </Alert>
        ) : (
          <Box
            sx={{
              display: "grid",
              gridTemplateColumns: {
                xs: "1fr",
                sm: "repeat(2, minmax(0, 1fr))",
                md: "repeat(3, minmax(0, 1fr))"
              },
              gap: 3
            }}
          >
            {filteredProducts.map((product) => (
              <ProductCard
                key={product.id}
                product={product}
                onAddToCart={handleAddToCart}
              />
            ))}
          </Box>
        )}
      </Stack>
    </Container>
  );
}
