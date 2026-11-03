
const USERS_KEY = "msoa-shop-users";
const SESSION_KEY = "msoa-shop-session";

// Demo accounts only. Never store real passwords in localStorage.
const demoUsers = [
  {
    id: "user-1",
    name: "Demo Customer",
    email: "demo@msoa.shop",
    password: "demo123",
    role: "CUSTOMER"
  }
];

function loadUsers() {
  try {
    const saved = localStorage.getItem(USERS_KEY);
    return saved ? JSON.parse(saved) : demoUsers;
  } catch {
    return demoUsers;
  }
}

function saveUsers(users) {
  localStorage.setItem(USERS_KEY, JSON.stringify(users));
}

function publicUser(user) {
  const { password, ...safeUser } = user;
  return safeUser;
}

export const authService = {
  // POST /api/auth/login
  async login(email, password) {
    const user = loadUsers().find(
      (item) =>
        item.email.toLowerCase() === email.trim().toLowerCase() &&
        item.password === password
    );

    if (!user) {
      throw new Error("Invalid email or password.");
    }

    const session = {
      user: publicUser(user),
      token: `mock-${crypto.randomUUID()}`
    };

    localStorage.setItem(SESSION_KEY, JSON.stringify(session));

    return session;
  },

  // POST /api/auth/register
  async register(name, email, password) {
    const users = loadUsers();
    const normalizedEmail = email.trim().toLowerCase();

    if (!name.trim() || !normalizedEmail || !password) {
      throw new Error("All fields are required.");
    }

    if (users.some((user) => user.email.toLowerCase() === normalizedEmail)) {
      throw new Error("Email already registered.");
    }

    const user = {
      id: crypto.randomUUID(),
      name: name.trim(),
      email: normalizedEmail,
      password,
      role: "CUSTOMER"
    };

    users.push(user);
    saveUsers(users);

    return publicUser(user);
  },

  // POST /api/auth/logout
  async logout() {
    localStorage.removeItem(SESSION_KEY);
    return { success: true };
  },

  // GET /api/auth/me
  async getCurrentUser() {
    try {
      const session = JSON.parse(localStorage.getItem(SESSION_KEY));
      return session?.user ?? null;
    } catch {
      return null;
    }
  }
};
