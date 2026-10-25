import WhatsAppButton from "./components/WhatsAppButton";
import { useEffect, useMemo, useState } from "react";
import {
  Search,
  ShoppingCart,
  MapPin,
  Menu,
  X,
  Plus,
  Minus,
  ArrowRight,
  Leaf,
  Truck,
  ShieldCheck,
  Heart,
} from "lucide-react";
import { fetchProducts, type ApiProduct, type AuthUser } from "./api";
import AuthPage from "./AuthPage";
import AdminDashboard from "./AdminDashboard";
import CustomerDashboard from "./CustomerDashboard";
import { API_URL, authFetch } from "./commerceApi";
import "./App.css";
import {useLanguage,languageOptions,type Language,} from "./LanguageContext";


type LanguageOption = {
  value: Language;
  label: string;
};


type Product = {
  id: number;
  name: string;
  description: string;
  price: number;
  unit: string;
  category: string;
  emoji: string;
  badge?: string;
  brand: string | null;
  stock_quantity: number;
  discount_percent?: number;
  image_url?: string | null;
  is_featured?: boolean;
  is_new_arrival?: boolean;
};

const categories = [
  { name: "All Products", emoji: "🛍️" },
  { name: "Rice & Grains", emoji: "🍚" },
  { name: "Lentils & Beans", emoji: "🫘" },
  { name: "Spices", emoji: "🌶️" },
  { name: "Fresh Produce", emoji: "🥬" },
  { name: "Pickles & Sauces", emoji: "🥭" },
  { name: "Tea & Drinks", emoji: "🍵" },
  { name: "Other Groceries", emoji: "🛍️" },
];

function getCategory(name: string): string {
  const value = name.toLowerCase();

  if (/rice|flour|atta|wheat|grain|poha/.test(value)) {
    return "Rice & Grains";
  }

  if (/dal|lentil|chickpea|chana|bean|rajma/.test(value)) {
    return "Lentils & Beans";
  }

  if (
    /masala|spice|turmeric|haldi|chilli powder|cumin|jeera|pepper|cardamom/.test(
      value,
    )
  ) {
    return "Spices";
  }

  if (/fresh|vegetable|chilli|potato|onion|tomato/.test(value)) {
    return "Fresh Produce";
  }

  if (/pickle|sauce|chutney/.test(value)) {
    return "Pickles & Sauces";
  }

  if (/tea|chai|coffee|drink|juice/.test(value)) {
    return "Tea & Drinks";
  }

  return "Other Groceries";
}

function getEmoji(category: string): string {
  const emojis: Record<string, string> = {
    "Rice & Grains": "🍚",
    "Lentils & Beans": "🫘",
    Spices: "🌶️",
    "Fresh Produce": "🥬",
    "Pickles & Sauces": "🥭",
    "Tea & Drinks": "🍵",
    "Other Groceries": "🛍️",
  };

  return emojis[category] ?? "🛍️";
}

function mapProduct(product: ApiProduct): Product {
  const category = getCategory(product.name);

  return {
    ...product,
    description: product.description || (product.brand
      ? `From ${product.brand}`
      : "An everyday grocery essential"),
    unit: "pack",
    category: product.category || category,
    emoji: getEmoji(category),
  };
}

function App() {
  const [showAuth, setShowAuth] = useState(false);
  const [showAdmin, setShowAdmin] = useState(false);
  const [showCustomer, setShowCustomer] = useState(false);
  const [relatedTo, setRelatedTo] = useState<Product | null>(null);
  const [relatedProducts, setRelatedProducts] = useState<Product[]>([]);
  const [signedInUser, setSignedInUser] = useState<AuthUser | null>(() => {
    // Remembered sessions survive browser restarts; unchecked sessions last only for this tab/session.
    try {
      const remembered = localStorage.getItem("desi-masala-user");
      const rememberedExpiry = Number(localStorage.getItem("desi-masala-auth-expires-at") || 0);
      if (remembered && rememberedExpiry > Date.now() && localStorage.getItem("desi-masala-access-token")) {
        return JSON.parse(remembered) as AuthUser;
      }
      if (remembered) {
        localStorage.removeItem("desi-masala-user");
        localStorage.removeItem("desi-masala-access-token");
        localStorage.removeItem("desi-masala-auth-expires-at");
      }
      const temporary = sessionStorage.getItem("desi-masala-user");
      const temporaryExpiry = Number(sessionStorage.getItem("desi-masala-auth-expires-at") || 0);
      if (temporary && temporaryExpiry > Date.now() && sessionStorage.getItem("desi-masala-access-token")) {
        return JSON.parse(temporary) as AuthUser;
      }
      sessionStorage.removeItem("desi-masala-user");
      sessionStorage.removeItem("desi-masala-access-token");
      sessionStorage.removeItem("desi-masala-auth-expires-at");
      return null;
    } catch { return null; }
  });

  function handleLogin(user: AuthUser, token: string, expiresIn: number, rememberMe: boolean) {
    const storage = rememberMe ? localStorage : sessionStorage;
    const otherStorage = rememberMe ? sessionStorage : localStorage;
    // Never store the password. The token expires server-side and is removed from storage at expiry.
    for (const key of ["desi-masala-access-token", "desi-masala-user", "desi-masala-auth-expires-at"]) otherStorage.removeItem(key);
    storage.setItem("desi-masala-access-token", token);
    storage.setItem("desi-masala-user", JSON.stringify(user));
    storage.setItem("desi-masala-auth-expires-at", String(Date.now() + expiresIn * 1000));
    setSignedInUser(user);
    setShowAuth(false);
    setShowCustomer(false);
    setShowAdmin(user.role === "admin");
  }

  function handleLogout() {
    for (const storage of [localStorage, sessionStorage]) {
      storage.removeItem("desi-masala-access-token");
      storage.removeItem("desi-masala-user");
      storage.removeItem("desi-masala-auth-expires-at");
    }
    setSignedInUser(null);
    setShowCustomer(false);
    setShowAdmin(false);
  }

  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [search, setSearch] = useState("");
  const [activeCategory, setActiveCategory] = useState("All Products");
  

const [cart, setCart] = useState<Record<number, number>>(() => {
  try {
    const savedCart = localStorage.getItem("desi-masala-cart");

    if (!savedCart) {
      return {};
    }

    const parsedCart: unknown = JSON.parse(savedCart);

    if (
      typeof parsedCart === "object" &&
      parsedCart !== null &&
      !Array.isArray(parsedCart)
    ) {
      return parsedCart as Record<number, number>;
    }

    return {};
  } catch (error) {
    console.error("Could not restore shopping cart:", error);
    return {};
  }
});


  useEffect(() => {
    try {
      localStorage.setItem(
        "desi-masala-cart",
        JSON.stringify(cart)
      );
    } catch (error) {
      console.error("Could not save shopping cart:", error);
    }
  }, [cart]);


  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [showCart, setShowCart] = useState(false);
  const [showCheckout, setShowCheckout] = useState(false);
  const [checkoutAddresses, setCheckoutAddresses] = useState<Array<{id:number;label:string;address_line1:string;postal_code:string;city:string;is_default:boolean}>>([]);
  const [checkoutWarehouses, setCheckoutWarehouses] = useState<Array<{id:number;name:string;location:string|null}>>([]);
  const [checkoutAddressId, setCheckoutAddressId] = useState("");
  const [checkoutWarehouseId, setCheckoutWarehouseId] = useState("");
  const [checkoutBusy, setCheckoutBusy] = useState(false);
  const [checkoutMessage, setCheckoutMessage] = useState("");
  const [checkoutError, setCheckoutError] = useState("");
  const [promoCode, setPromoCode] = useState("");
  const [promoBusy, setPromoBusy] = useState(false);
  const [discountPreview, setDiscountPreview] = useState<{subtotal:string;discount_percent:string;discount_amount:string;total:string;discount_reason:string;promo_applied:boolean}|null>(null);
  useEffect(() => { setDiscountPreview(null); }, [cart, checkoutAddressId, checkoutWarehouseId]);
  const { language, setLanguage, t } = useLanguage();
  const [favourites, setFavourites] = useState<number[]>([]);

  useEffect(() => {
    if (!showCheckout || !signedInUser) return;
    const token = localStorage.getItem("desi-masala-access-token") || sessionStorage.getItem("desi-masala-access-token") || "";
    let cancelled = false;
    async function loadCheckoutOptions() {
      setCheckoutError(""); setCheckoutMessage("");
      try {
        const [addressesResponse, warehousesResponse] = await Promise.all([
          authFetch(`${API_URL}/commerce/customer/addresses`, token), fetch(`${API_URL}/commerce/warehouses`),
        ]);
        if (!addressesResponse.ok) throw new Error("Could not load your saved addresses. Please sign in again.");
        if (!warehousesResponse.ok) throw new Error("Could not load delivery warehouse options.");
        const addresses = await addressesResponse.json(); const warehouses = await warehousesResponse.json();
        if (!cancelled) {
          setCheckoutAddresses(addresses); setCheckoutWarehouses(warehouses);
          setCheckoutAddressId((current) => current || String(addresses.find((a: {is_default:boolean})=>a.is_default)?.id ?? addresses[0]?.id ?? ""));
          setCheckoutWarehouseId((current) => current || String(warehouses[0]?.id ?? ""));
        }
      } catch (e) { if (!cancelled) setCheckoutError(e instanceof Error ? e.message : "Could not load checkout options."); }
    }
    void loadCheckoutOptions();
    return () => { cancelled = true; };
  }, [showCheckout, signedInUser]);

  async function submitCheckout() {
    if (!signedInUser) { setShowCheckout(false); setShowCart(false); setShowAuth(true); return; }
    if (!checkoutAddressId || !checkoutWarehouseId) { setCheckoutError("Add a delivery address and make sure a warehouse is configured before checkout."); return; }
    const token = localStorage.getItem("desi-masala-access-token") || sessionStorage.getItem("desi-masala-access-token") || "";
    setCheckoutBusy(true); setCheckoutError(""); setCheckoutMessage("");
    try {
      const response = await authFetch(`${API_URL}/commerce/checkout`, token, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ items: Object.entries(cart).filter(([, quantity]) => Number(quantity) > 0).map(([product_id, quantity]) => ({ product_id: Number(product_id), quantity: Number(quantity) })), warehouse_id: Number(checkoutWarehouseId), address_id: Number(checkoutAddressId), idempotency_key: crypto.randomUUID(), promo_code: promoCode.trim() || null }) });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || `Checkout failed (${response.status}).`);
      const orderIds = (body.orders || []).map((order: { id: number }) => order.id);
      if (!orderIds.length) throw new Error("The order was created without an order number. Please contact support before trying again.");
      setCart({});
      setCheckoutMessage(`Order ${orderIds.map((id: number) => `#${id}`).join(", ")} placed successfully. Payment is manual for now. Please arrange payment with the store; your order will show as pending until an administrator confirms receipt.`);
      await fetchProducts(language).then((data) => setProducts(data.map(mapProduct)));
    } catch (e) { setCheckoutError(e instanceof Error ? e.message : "Checkout failed."); }
    finally { setCheckoutBusy(false); }
  }

  async function applyPromoCode() {
    // Promo codes are optional. An empty value means "continue without a promo".
    if (!promoCode.trim()) {
      setDiscountPreview(null);
      setCheckoutError("");
      setCheckoutMessage("");
      return;
    }
    if (!signedInUser) { setCheckoutError("Please sign in to apply a promo code."); return; }
    if (!checkoutAddressId || !checkoutWarehouseId) { setCheckoutError("Choose a delivery address and warehouse first."); return; }
    const token = localStorage.getItem("desi-masala-access-token") || sessionStorage.getItem("desi-masala-access-token") || "";
    setPromoBusy(true); setCheckoutError(""); setDiscountPreview(null);
    try {
      const response = await authFetch(`${API_URL}/commerce/checkout/discount-preview`, token, { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({items:Object.entries(cart).filter(([,q])=>Number(q)>0).map(([product_id,quantity])=>({product_id:Number(product_id),quantity:Number(quantity)})),warehouse_id:Number(checkoutWarehouseId),address_id:Number(checkoutAddressId),idempotency_key:crypto.randomUUID(),promo_code:promoCode.trim()||null}) });
      const body=await response.json(); if(!response.ok) throw new Error(body.detail||t("invalidPromo")); setDiscountPreview(body); setCheckoutMessage(body.promo_applied ? `${t("discountApplied")}: ${promoCode.toUpperCase()}` : `${t("discountApplied")}: ${body.discount_percent}%`);
    } catch(e) { setCheckoutError(e instanceof Error?e.message:t("invalidPromo")); } finally { setPromoBusy(false); }
  }

  useEffect(() => {
    let cancelled = false;

    async function loadProducts() {
      try {
        setLoading(true);
        setError("");

        const data = await fetchProducts(language);

        if (!cancelled) {
          setProducts(data.map(mapProduct));
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Something went wrong while loading products.",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadProducts();

    return () => {
      cancelled = true;
    };
  }, [language]);

  const filteredProducts = useMemo(() => {
    const query = search.trim().toLowerCase();

    return products.filter((product) => {
      const matchesCategory =
        activeCategory === "All Products" ||
        product.category === activeCategory;

      const matchesSearch =
        product.name.toLowerCase().includes(query) ||
        product.description.toLowerCase().includes(query) ||
        (product.brand ?? "").toLowerCase().includes(query) ||
        product.category.toLowerCase().includes(query);

      return matchesCategory && matchesSearch;
    });
  }, [products, search, activeCategory]);

  const cartCount = Object.values(cart).reduce(
    (total, quantity) => total + quantity,
    0,
  );

  const priceAfterDiscount = (product: Product) => product.price * (100 - (product.discount_percent ?? 0)) / 100;
  const cartTotal = products.reduce(
    (total, product) => total + priceAfterDiscount(product) * (cart[product.id] ?? 0),
    0,
  );

  function changeQuantity(productId: number, amount: number) {
    const product = products.find((item) => item.id === productId);

    if (!product) return;

    setCart((previous) => {
      const currentQuantity = previous[productId] ?? 0;
      const nextQuantity = currentQuantity + amount;

      if (nextQuantity <= 0) {
        const updated = { ...previous };
        delete updated[productId];
        return updated;
      }

      if (nextQuantity > product.stock_quantity) {
        return previous;
      }

      return {
        ...previous,
        [productId]: nextQuantity,
      };
    });
  }

  

  useEffect(() => {
    if (!signedInUser) return;
    const token = localStorage.getItem("desi-masala-access-token") || sessionStorage.getItem("desi-masala-access-token") || "";
    if (!token) return;
    let cancelled = false;
    void authFetch(`${API_URL}/engagement/favorites`, token).then(async response => {
      if (response.ok) {
        const rows = await response.json() as Array<{id:number}>;
        if (!cancelled) setFavourites(rows.map(row => row.id));
      }
    }).catch(() => undefined);
    return () => { cancelled = true; };
  }, [signedInUser]);

  async function requestBackInStock(productId: number) {
    if (!signedInUser) { setShowAuth(true); return; }
    const token = localStorage.getItem("desi-masala-access-token") || sessionStorage.getItem("desi-masala-access-token") || "";
    try {
      const response = await authFetch(`${API_URL}/commerce/customer/products/${productId}/back-in-stock-alert`, token, { method: "POST" });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "Could not subscribe to stock alert.");
      setError("");
      window.alert(body.message || "We'll alert you when this product is back in stock.");
    } catch (e) { setError(e instanceof Error ? e.message : "Could not subscribe to stock alert."); }
  }

  async function toggleFavourite(productId: number) {
    const wasFavourite = favourites.includes(productId);
    setFavourites(previous => wasFavourite ? previous.filter(id => id !== productId) : [...previous, productId]);
    const token = localStorage.getItem("desi-masala-access-token") || sessionStorage.getItem("desi-masala-access-token") || "";
    if (!signedInUser || !token) return;
    try {
      const response = await authFetch(`${API_URL}/engagement/favorites/${productId}`, token, { method: wasFavourite ? "DELETE" : "POST" });
      if (!response.ok) throw new Error("Could not sync favorite.");
    } catch {
      setFavourites(previous => wasFavourite ? [...previous, productId] : previous.filter(id => id !== productId));
      setError("Please sign in again to save favorites to your account.");
    }
  }

  function browseProducts() {
    document.getElementById("shop")?.scrollIntoView({
      behavior: "smooth",
    });
  }

  function selectCategory(categoryName: string) {
    setActiveCategory(categoryName);
    setMobileMenuOpen(false);
  }

  if (showAuth) {
    return <AuthPage onBack={() => setShowAuth(false)} onLogin={handleLogin} />;
  }

  if (showCustomer && signedInUser) {
    const token = localStorage.getItem("desi-masala-access-token") || sessionStorage.getItem("desi-masala-access-token") || "";
    return <CustomerDashboard token={token} onBack={() => setShowCustomer(false)} />;
  }

  if (showAdmin && signedInUser?.role === "admin") {
    const token = localStorage.getItem("desi-masala-access-token") || sessionStorage.getItem("desi-masala-access-token") || "";
    return <AdminDashboard token={token} onBack={() => setShowAdmin(false)} />;
  }

  return (
    <div className="app">
      <div className="announcement">
        <Leaf size={15} />
        <span>A little taste of home, delivered to your door.</span>
      </div>

      <header className="site-header">
        <a className="brand" href="#" aria-label="Desi Masala home">
          <span className="brand-icon">🌿</span>
          <span className="brand-copy">
            <strong>desi masala</strong>
            <small>A TASTE OF HOME</small>
          </span>
        </a>

        <div className="delivery-location">
          <MapPin size={17} />
          <span>
            <small>Delivering to</small>
            <strong>Germany</strong>
          </span>
        </div>

        <label className="search-box">
          <Search size={19} />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={t("search")}
            aria-label="Search products"
          />
          {search && (
            <button
              className="clear-search"
              onClick={() => setSearch("")}
              aria-label="Clear search"
            >
              <X size={16} />
            </button>
          )}
        </label>

        {signedInUser ? (
          <div className="account-actions">
            <span className="account-greeting">Hi, {signedInUser.name.split(" ")[0]}</span>
            {signedInUser.role === "admin" ? <button className="account-button" onClick={() => setShowAdmin(true)}>{t("adminDashboard")}</button> : <button className="account-button" onClick={() => setShowCustomer(true)}>{t("myAccount")}</button>}
            <button className="account-button" onClick={handleLogout}>{t("signOut")}</button>
          </div>
        ) : (
          <button className="account-button" onClick={() => setShowAuth(true)}>{t("signIn")}</button>
        )}
        <label className="language-picker" aria-label={t("language")}><span>{t("language")}</span><select value={language} onChange={e=>setLanguage(e.target.value as typeof language)}>{languageOptions.map((option: LanguageOption) => (<option key={option.value} value={option.value}>{option.label}</option>))}
</select></label>
        <WhatsAppButton />
        <button
          className="cart-button"
          onClick={() => setShowCart(true)}
          aria-label={`Open shopping cart with ${cartCount} items`}
        >
          <ShoppingCart size={20} />
          <span>{t("cart")}</span>
          <span className="cart-count">{cartCount}</span>
        </button>

        <button
          className="mobile-menu-button"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          aria-label="Toggle menu"
        >
          {mobileMenuOpen ? <X /> : <Menu />}
        </button>
      </header>

      {mobileMenuOpen && (
        <div className="mobile-search">
          <label className="search-box">
            <Search size={19} />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search groceries..."
            />
          </label>
          <button onClick={() => setShowCart(true)}>
            <ShoppingCart size={18} />
            View cart ({cartCount})
          </button>
        </div>
      )}

      <nav className="category-nav" aria-label="Product categories">
        {categories.map((category) => (
          <button
            key={category.name}
            className={
              activeCategory === category.name ? "nav-active" : ""
            }
            onClick={() => {
              selectCategory(category.name);
              browseProducts();
            }}
          >
            {category.name}
          </button>
        ))}
      </nav>

      <main>
        <section className="hero">
          <div className="hero-content">
            <span className="eyebrow">
              <Leaf size={15} /> YOUR INDIAN GROCERY STORE
            </span>

            <h1>
              Bring the taste
              <br />
              of <span>home</span> to your table.
            </h1>

            <p>
              From fragrant spices to everyday essentials,
              discover the flavours you grew up loving.
            </p>

            <button className="primary-button" onClick={browseProducts}>
              Explore groceries <ArrowRight size={18} />
            </button>

            <div className="hero-note">
              <span>✦</span> Carefully selected everyday essentials
            </div>
          </div>

          <div
            className="hero-art"
            aria-label="Indian groceries illustration"
          >
            <div className="hero-circle">
              <span className="hero-spice">🌶️</span>
              <span className="hero-rice">🍚</span>
              <span className="hero-leaf">🌿</span>
              <span className="hero-turmeric">🫚</span>
              <span className="hero-bowl">🥘</span>
            </div>

            <div className="floating-note">
              <span>❤️</span>
              <div>
                <strong>Made for your kitchen</strong>
                <small>Flavours worth sharing</small>
              </div>
            </div>
          </div>

          <div className="hero-decoration decoration-one">✳</div>
          <div className="hero-decoration decoration-two">✳</div>
        </section>

        <section className="benefits" aria-label="Store benefits">
          <div className="benefit">
            <span className="benefit-icon">
              <Truck size={21} />
            </span>
            <div>
              <strong>Convenient delivery</strong>
              <small>Shop from home</small>
            </div>
          </div>

          <div className="benefit">
            <span className="benefit-icon">
              <Leaf size={21} />
            </span>
            <div>
              <strong>Quality essentials</strong>
              <small>Selected with care</small>
            </div>
          </div>

          <div className="benefit">
            <span className="benefit-icon">
              <ShieldCheck size={21} />
            </span>
            <div>
              <strong>Secure shopping</strong>
              <small>Checkout coming soon</small>
            </div>
          </div>
        </section>

        <section className="shop-section" id="shop">
          <div className="section-heading">
            <div>
              <span className="section-kicker">
                GOOD FOOD, GOOD MOOD
              </span>
              <h2>
                Shop your <span>favourites</span>
              </h2>
              <p>
                Everyday essentials to make every meal feel special.
              </p>
            </div>

            <span className="product-total">
              {loading ? "Loading..." : `${filteredProducts.length} products`}
            </span>
          </div>

          <div className="category-chips">
            {categories.map((category) => (
              <button
                key={category.name}
                className={
                  activeCategory === category.name ? "chip-active" : ""
                }
                onClick={() => selectCategory(category.name)}
              >
                <span>{category.emoji}</span> {category.name}
              </button>
            ))}
          </div>

          {loading ? (
            <div className="empty-products">
              <span>🛍️</span>
              <h3>Loading groceries...</h3>
              <p>Fetching the latest products from our store.</p>
            </div>
          ) : error ? (
            <div className="empty-products">
              <span>⚠️</span>
              <h3>We couldn't load the products</h3>
              <p>{error}</p>
              <button
                className="primary-button"
                onClick={() => window.location.reload()}
              >
                Try again
              </button>
            </div>
          ) : filteredProducts.length > 0 ? (
            <div className="product-grid">
              {filteredProducts.map((product) => (
                <article className="product-card" key={product.id}>
                  <div className={`product-visual visual-${product.id}`}>
                    {product.badge && (
                      <span className="product-badge">
                        {product.badge}
                      </span>
                    )}

                    <button
                      className={`favourite-button ${
                        favourites.includes(product.id)
                          ? "is-favourite"
                          : ""
                      }`}
                      onClick={() => toggleFavourite(product.id)}
                      aria-label={
                        favourites.includes(product.id)
                          ? `Remove ${product.name} from favourites`
                          : `Add ${product.name} to favourites`
                      }
                    >
                      <Heart
                        size={18}
                        fill={
                          favourites.includes(product.id)
                            ? "currentColor"
                            : "none"
                        }
                      />
                    </button>

                    <span className="product-emoji">
                      {product.emoji}
                    </span>
                    <span className="product-category">
                      {product.category}
                    </span>
                  </div>

                  <div className="product-info">
                    <h3><button className="product-title-button" onClick={async () => { setRelatedTo(product); try { const r = await fetch(`${API_URL}/commerce/products/${product.id}/related`); if (r.ok) { const data = await r.json(); setRelatedProducts(data.map((p: ApiProduct) => mapProduct(p))); } } catch { setRelatedProducts([]); } }}>{product.name}</button></h3>
                    <p>{product.description}</p>

                    <small>
                      {product.stock_quantity > 0
                        ? `${product.stock_quantity} available`
                        : "Out of stock"}
                    </small>

                    <div className="product-purchase">
                      <div className="product-price">
                        <strong>
                          €{priceAfterDiscount(product).toFixed(2)}
                        </strong>
                        {(product.discount_percent ?? 0) > 0 && <small className="sale-old-price">€{product.price.toFixed(2)} · {product.discount_percent}% off</small>}
                        <small>/ {product.unit}</small>
                      </div>

                      {(cart[product.id] ?? 0) === 0 ? (
                        <button
                          className="add-button"
                          disabled={product.stock_quantity <= 0}
                          onClick={() => changeQuantity(product.id, 1)}
                          aria-label={`Add ${product.name} to cart`}
                        >
                          <Plus size={17} />
                          {product.stock_quantity <= 0 ? "Sold out" : "Add"}
                        </button>
                      ) : (
                        <div className="quantity-control">
                          <button
                            onClick={() => changeQuantity(product.id, -1)}
                            aria-label={`Remove one ${product.name}`}
                          >
                            <Minus size={15} />
                          </button>

                          <strong>{cart[product.id]}</strong>

                          <button
                            disabled={
                              (cart[product.id] ?? 0) >=
                              product.stock_quantity
                            }
                            onClick={() => changeQuantity(product.id, 1)}
                            aria-label={`Add one ${product.name}`}
                          >
                            <Plus size={15} />
                          </button>
                        </div>
                      )}
                    </div>
                    {product.stock_quantity <= 0 && <button className="stock-alert-button" onClick={() => void requestBackInStock(product.id)}>Alert me when available</button>}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="empty-products">
              <span>🔎</span>
              <h3>No products found</h3>
              <p>Try another search or browse all our groceries.</p>
              <button
                className="primary-button"
                onClick={() => {
                  setSearch("");
                  setActiveCategory("All Products");
                }}
              >
                Show all products
              </button>
            </div>
          )}
        </section>

        {relatedTo && <section className="shop-section related-section">
          <div className="section-heading"><div><span className="section-kicker">YOU MAY ALSO LIKE</span><h2>Pairs well with <span>{relatedTo.name}</span></h2><p>Similar groceries and customer favourites.</p></div><button className="continue-shopping" onClick={() => { setRelatedTo(null); setRelatedProducts([]); }}>Close recommendations</button></div>
          <div className="product-grid">{relatedProducts.filter(p => p.stock_quantity > 0).map(product => <article className="product-card" key={product.id}><div className={`product-visual visual-${product.id}`}><span className="product-emoji">{product.emoji}</span><span className="product-category">{product.category}</span></div><div className="product-info"><h3>{product.name}</h3><p>{product.description}</p><div className="product-purchase"><div className="product-price"><strong>€{priceAfterDiscount(product).toFixed(2)}</strong></div><button className="add-button" onClick={() => changeQuantity(product.id,1)}><Plus size={16}/> Add</button></div></div></article>)}</div>
          {relatedProducts.length === 0 && <p>There are no related products available yet. Add categories to products in the admin dashboard to improve recommendations.</p>}
        </section>}

        <section className="newsletter">
          <div>
            <span className="section-kicker">A LITTLE NOTE FROM US</span>
            <h2>Good things are coming.</h2>
            <p>
              We're building your favourite place for Indian groceries in
              Germany.
            </p>
          </div>
          <span className="newsletter-art">🌼</span>
        </section>
      </main>

      <footer className="site-footer">
        <a className="brand footer-brand" href="#">
          <span className="brand-icon">🌿</span>
          <span className="brand-copy">
            <strong>desi masala</strong>
            <small>A TASTE OF HOME</small>
          </span>
        </a>

        <p>Good food brings us closer. Made with a little extra love.</p>
        <span>© {new Date().getFullYear()} Desi Masala</span>
      </footer>

      {showCart && (
        <div
          className="cart-overlay"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setShowCart(false);
            }
          }}
        >
          <aside
            className="cart-drawer"
            role="dialog"
            aria-modal="true"
            aria-label="Your shopping cart"
          >
            <div className="cart-header">
              <div>
                <span className="section-kicker">YOUR BASKET</span>
                <h2>{t("shoppingCart")} ({cartCount})</h2>
              </div>

              <button
                className="close-cart"
                onClick={() => setShowCart(false)}
                aria-label="Close cart"
              >
                <X />
              </button>
            </div>

            {cartCount === 0 ? (
              <div className="empty-cart">
                <span>🛒</span>
                <h3>Your basket is waiting</h3>
                <p>Add some favourites and they'll show up here.</p>
                <button
                  className="primary-button"
                  onClick={() => {
                    setShowCart(false);
                    browseProducts();
                  }}
                >
                  Start shopping <ArrowRight size={17} />
                </button>
              </div>
            ) : (
              <>
                <div className="cart-items">
                  {products
                    .filter((product) => (cart[product.id] ?? 0) > 0)
                    .map((product) => (
                      <div className="cart-item" key={product.id}>
                        <div
                          className={`cart-item-emoji visual-${product.id}`}
                        >
                          {product.emoji}
                        </div>

                        <div className="cart-item-info">
                          <strong>{product.name}</strong>
                          <small>{product.unit}</small>

                          <div className="quantity-control">
                            <button
                              onClick={() =>
                                changeQuantity(product.id, -1)
                              }
                              aria-label={`Remove one ${product.name}`}
                            >
                              <Minus size={14} />
                            </button>

                            <strong>{cart[product.id]}</strong>

                            <button
                              disabled={
                                (cart[product.id] ?? 0) >=
                                product.stock_quantity
                              }
                              onClick={() =>
                                changeQuantity(product.id, 1)
                              }
                              aria-label={`Add one ${product.name}`}
                            >
                              <Plus size={14} />
                            </button>
                          </div>
                        </div>

                        <strong className="cart-item-price">
                          €
                          {(
                            product.price * cart[product.id]
                          ).toFixed(2)}
                        </strong>
                      </div>
                    ))}
                </div>

                <div className="cart-summary">
                  <div className="cart-subtotal">
                    <span>Subtotal</span>
                    <strong>€{cartTotal.toFixed(2)}</strong>
                  </div>

                  <small>
                    Delivery fees and any applicable taxes will be confirmed
                    at checkout.
                  </small>

                  <button
                    className="primary-button checkout-button"
                    onClick={() => { setCheckoutMessage(""); setCheckoutError(""); setShowCheckout(true); }}
                  >
                    {t("continueCheckout")} <ArrowRight size={18} />
                  </button>

                  <button
                    className="continue-shopping"
                    onClick={() => setShowCart(false)}
                  >
                    Continue shopping
                  </button>
                  {checkoutMessage && <div className="checkout-feedback checkout-success" role="status">{checkoutMessage}</div>}
                  {showCheckout && <div className="checkout-options"><h3>{t("deliveryOrder")}</h3>
                    {!signedInUser && <p>Please sign in before placing an order.</p>}
                    {signedInUser && <>
                      <label>{t("deliveryAddress")}<select value={checkoutAddressId} onChange={e=>setCheckoutAddressId(e.target.value)}><option value="">{t("chooseAddress")}</option>{checkoutAddresses.map(a=><option key={a.id} value={a.id}>{a.label}: {a.address_line1}, {a.postal_code} {a.city}{a.is_default?" (default)":""}</option>)}</select></label>
                      {checkoutAddresses.length===0 && <p>Add an address in My account before checking out.</p>}
                      <label>{t("warehouse")}<select value={checkoutWarehouseId} onChange={e=>setCheckoutWarehouseId(e.target.value)}><option value="">{t("chooseWarehouse")}</option>{checkoutWarehouses.map(w=><option key={w.id} value={w.id}>{w.name}{w.location?` — ${w.location}`:""}</option>)}</select></label>
                    </>}
                    {checkoutError && <div className="checkout-feedback checkout-error" role="alert">{checkoutError}</div>}
                    <div className="promo-code-box"><label htmlFor="checkout-promo-code">{t("promoCode")}</label><div className="promo-code-row"><input id="checkout-promo-code" value={promoCode} onChange={e=>{setPromoCode(e.target.value.toUpperCase());setDiscountPreview(null);setCheckoutError("");setCheckoutMessage("");}} placeholder={t("promoPlaceholder")} maxLength={60} autoComplete="off" aria-label={t("promoCode")}/><button type="button" className="promo-apply-button" disabled={promoBusy||cartCount===0} onClick={()=>void applyPromoCode()}>{promoBusy?"…":t("apply")}</button></div></div>
                    {discountPreview && <div className="discount-preview" role="status"><div><span>{t("subtotal")}</span><strong>€{Number(discountPreview.subtotal).toFixed(2)}</strong></div><div><span>{t("discount")} ({discountPreview.discount_percent}%)</span><strong>-€{Number(discountPreview.discount_amount).toFixed(2)}</strong></div><div className="discount-total"><span>{t("total")}</span><strong>€{Number(discountPreview.total).toFixed(2)}</strong></div><small>{discountPreview.discount_reason}</small></div>}
                    <button className="primary-button checkout-button" disabled={checkoutBusy||cartCount===0} onClick={()=>void submitCheckout()}>{checkoutBusy?t("placingOrder"):t("placeOrder")}</button>
                    <small>Manual payment for now. No online payment is taken; the store will confirm payment after receiving it.</small>
                  </div>}
                </div>
              </>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}

export default App;
