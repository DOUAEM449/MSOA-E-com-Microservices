
import {
  Box,
  Button,
  Container,
  Paper,
  Stack,
  Typography
} from "@mui/material";

import {
  ArrowForwardRounded,
  StorefrontOutlined
} from "@mui/icons-material";

import Navbar from "./components/Navbar";

export default function App() {
  return (
    <Box
      sx={{
        minHeight: "100vh",
        bgcolor: "#f8fafc"
      }}
    >
      <Navbar />

      <Box component="main">
        <Container
          maxWidth="lg"
          sx={{
            py: { xs: 4, sm: 6, md: 10 }
          }}
        >
          <Paper
            elevation={0}
            sx={{
              px: { xs: 3, sm: 5, md: 8 },
              py: { xs: 6, sm: 8, md: 12 },
              borderRadius: { xs: 3, md: 5 },
              bgcolor: "#e3f2fd",
              textAlign: "center"
            }}
          >
            <Stack
              spacing={{ xs: 2, md: 3 }}
              alignItems="center"
            >
              <StorefrontOutlined
                sx={{
                  fontSize: { xs: 48, md: 64 },
                  color: "primary.main"
                }}
              />

              <Typography
                component="h1"
                variant="h2"
                fontWeight={800}
                sx={{
                  fontSize: {
                    xs: "2rem",
                    sm: "2.75rem",
                    md: "3.75rem"
                  },
                  lineHeight: 1.15
                }}
              >
                Welcome to MSOA Shop
              </Typography>

              <Typography
                variant="h6"
                color="text.secondary"
                sx={{
                  fontSize: {
                    xs: "1rem",
                    md: "1.25rem"
                  },
                  maxWidth: 550
                }}
              >
                Discover great products at great prices.
                Your next favorite item is just a click away.
              </Typography>

              <Button
                variant="contained"
                size="large"
                endIcon={<ArrowForwardRounded />}
                sx={{
                  mt: 2,
                  px: 4,
                  py: 1.5,
                  borderRadius: 2,
                  width: { xs: "100%", sm: "auto" },
                  maxWidth: { xs: 320, sm: "none" },
                  textTransform: "none",
                  fontWeight: 600
                }}
              >
                Explore Products
              </Button>
            </Stack>
          </Paper>
        </Container>
      </Box>
    </Box>
  );
}
