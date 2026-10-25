import { useCallback, useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { ArrowLeft, Boxes, ClipboardList, IndianRupee, AlertTriangle, Upload, PackagePlus, RefreshCw, LayoutDashboard, Package, ShoppingCart, MessageSquareText, LifeBuoy, Warehouse } from "lucide-react";
import { API_URL, authFetch } from "./commerceApi";
import "./AdminDashboard.css";
import { useLanguage, languageOptions } from "./LanguageContext";
import AdminSupportPanel from "./AdminSupportPanel";
import { AdminEngagement } from "./EngagementPanels";

type Overview = {
  products_count: number;
  orders: { order_count: number; pending_orders: number; paid_revenue: number | string; pending_revenue: number | string };
  low_stock: Array<{ id: number; name: string; stock_quantity: number }>;
  expiring_stock: Array<{ id: number; name: string; quantity_remaining: number; expiry_date: string; unit_cost: number; warehouse_name: string }>;
  average_costs: Array<{ id: number; name: string; batch_quantity: number; weighted_average_cost: number | string | null }>;
  fast_selling: Array<{ id: number; name: string; units_sold: number }>;
  most_requested: Array<{ id: number; name: string; request_count: number; stock_quantity: number }>;
};
type AdminProduct = { id: number; name: string; price: number|string; brand: string|null; description: string|null; category: string|null; image_url: string|null; discount_percent: number|string; is_featured: boolean; is_new_arrival: boolean; active: boolean; stock_quantity: number; expiry_discount_percent?: number|string; expiry_discount_until?: string|null };
type Analytics = {
  daily_sales: Array<{ day: string; sales: number | string }>;
  monthly_comparison: Array<{ month: string; investment: number | string; sales: number | string }>;
  monthly_profit_loss: Array<{ month: string; revenue: number | string; cost: number | string; profit: number | string }>;
};
type AdminSection = "discount_usage" | "dashboard" | "inventory" | "low_stock" | "expiry" | "stock_cost" | "stock_import" | "fast_selling" | "product_requests" | "products" | "add_product" | "orders" | "feedback" | "feature_requests" | "support";
type AdminNotification = { id: number; kind: string; title: string; message: string; read_at: string | null; created_at: string };
type Order = { id: number; customer_name: string; email: string; product_name: string; quantity: number; amount: number | string; status: string; payment_status: string; created_at: string; carrier?: string | null; tracking_number?: string | null; tracking_url?: string | null; estimated_delivery?: string | null };

export default function AdminDashboard({ token, onBack }: { token: string; onBack: () => void }) {
  const { language, setLanguage } = useLanguage();
  const [overview, setOverview] = useState<Overview | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);
  const [products, setProducts] = useState<AdminProduct[]>([]);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [notifications, setNotifications] = useState<AdminNotification[]>([]);
  const [discountUsage, setDiscountUsage] = useState<Array<{id:number;promo_code:string;discount_percent:number|string;discount_amount:number|string;order_ids:number[];created_at:string;customer_name:string;email:string}>>([]);
  const [activeSection, setActiveSection] = useState<AdminSection>("dashboard");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [trackingDraft, setTrackingDraft] = useState<Record<number, { carrier: string; tracking_number: string; tracking_url: string; estimated_delivery: string }>>({});
  const [newProduct, setNewProduct] = useState({ name: "", price: "", brand: "", category: "Spices", description: "", discount_percent: "0", is_featured: false, is_new_arrival: true });

  const load = useCallback(async () => {
    try {
      const [o, ord, prods, analyticsResponse, notificationsResponse] = await Promise.all([
        authFetch(`${API_URL}/commerce/admin/overview`, token),
        authFetch(`${API_URL}/commerce/admin/orders`, token),
        authFetch(`${API_URL}/commerce/admin/products`, token),
        authFetch(`${API_URL}/commerce/admin/analytics`, token),
        authFetch(`${API_URL}/commerce/admin/notifications`, token),
      ]);
      const discountResponse = await authFetch(`${API_URL}/commerce/admin/discount-usage`, token);
      const [overviewData, orderData, productData, notificationData, discountUsageData] = await Promise.all([o.json().catch(() => null), ord.json().catch(() => null), prods.json().catch(() => null), notificationsResponse.json().catch(() => []), discountResponse.ok ? discountResponse.json().catch(() => []) : Promise.resolve([])]);
      if (!o.ok) throw new Error(typeof overviewData?.detail === "string" ? overviewData.detail : `Overview request failed (${o.status})`);
      if (!ord.ok) throw new Error(typeof orderData?.detail === "string" ? orderData.detail : `Orders request failed (${ord.status})`);
      if (!prods.ok) throw new Error(typeof productData?.detail === "string" ? productData.detail : `Products request failed (${prods.status})`);
      setOverview(overviewData); setOrders(orderData); setProducts(productData);
      if (analyticsResponse.ok) setAnalytics(await analyticsResponse.json());
      if (notificationsResponse.ok && Array.isArray(notificationData)) setNotifications(notificationData);
      if (Array.isArray(discountUsageData)) setDiscountUsage(discountUsageData);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not load admin data."); }
  }, [token]);
  useEffect(() => { const timer = window.setTimeout(() => { void load(); }, 0); return () => window.clearTimeout(timer); }, [load]);
  async function runNotificationCampaigns() {
    setError(""); setMessage("");
    try {
      const r = await authFetch(`${API_URL}/engagement/admin/run-notification-campaigns`, token, { method: "POST" });
      if (!r.ok) throw new Error(await responseError(r));
      const result = await r.json();
      setMessage(`Offer alerts checked: ${result.birthday_notifications ?? 0} birthdays, ${result.discount_notifications ?? 0} discounts, ${result.expiry_notifications ?? 0} expiry alerts created.`);
      await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not run offer alerts."); }
  }
  async function markNotificationRead(id: number) {
    try {
      const r = await authFetch(`${API_URL}/commerce/admin/notifications/${id}/read`, token, { method: "PATCH" });
      if (!r.ok) throw new Error(await responseError(r));
      setNotifications(current => current.map(n => n.id === id ? { ...n, read_at: new Date().toISOString() } : n));
    } catch (e) { setError(e instanceof Error ? e.message : "Could not mark notification read."); }
  }
  async function responseError(r: Response) { try { const b = await r.json(); if (typeof b.detail === "string") return b.detail; if (Array.isArray(b.detail)) return b.detail.map((x: { msg?: string }) => x.msg || JSON.stringify(x)).join(", "); return `Request failed (${r.status})`; } catch { return `Request failed (${r.status})`; } }

  async function confirmManualPayment(orderId: number) {
    if (!window.confirm(`Confirm that manual payment for order #${orderId} has actually been received?`)) return;
    setMessage(""); setError("");
    try {
      const r = await authFetch(`${API_URL}/commerce/admin/orders/${orderId}/confirm-payment`, token, { method: "POST" });
      if (!r.ok) throw new Error(await responseError(r));
      setMessage(`Payment confirmed for order #${orderId}.`); await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not confirm payment."); }
  }
  async function updateStatus(orderId: number, status: string, shipment?: { carrier?: string; tracking_number?: string; tracking_url?: string; estimated_delivery?: string }) {
    setMessage(""); setError("");
    try {
      const r = await authFetch(`${API_URL}/commerce/admin/orders/${orderId}/status`, token, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status, ...shipment }) });
      if (!r.ok) throw new Error(await responseError(r));
      setMessage(`Order #${orderId} updated.`); await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Update failed."); }
  }
  async function createProduct(e: FormEvent) {
    e.preventDefault(); setBusy(true); setMessage(""); setError("");
    try {
      const r = await authFetch(`${API_URL}/commerce/admin/products`, token, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...newProduct, price: Number(newProduct.price), discount_percent: Number(newProduct.discount_percent), active: true }) });
      if (!r.ok) throw new Error(await responseError(r));
      setMessage("Product created successfully."); setNewProduct({ name: "", price: "", brand: "", category: "Spices", description: "", discount_percent: "0", is_featured: false, is_new_arrival: true }); await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not create product."); } finally { setBusy(false); }
  }
  async function importStock() {
    if (!uploadFile) return;
    setBusy(true); setMessage(""); setError("");
    try {
      const form = new FormData(); form.append("file", uploadFile);
      const r = await authFetch(`${API_URL}/commerce/admin/stock/import-csv`, token, { method: "POST", body: form });
      if (!r.ok) throw new Error(await responseError(r));
      const result = await r.json(); setMessage(`${result.rows_imported} stock rows imported.`); setUploadFile(null); await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Stock import failed."); } finally { setBusy(false); }
  }
  async function saveProduct(product: AdminProduct) {
    setMessage(""); setError("");
    try {
      const r = await authFetch(`${API_URL}/commerce/admin/products/${product.id}`, token, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: product.name, price: Number(product.price), brand: product.brand, description: product.description, category: product.category || "Other Groceries", image_url: product.image_url, discount_percent: Number(product.discount_percent), is_featured: product.is_featured, is_new_arrival: product.is_new_arrival, active: product.active }) });
      if (!r.ok) throw new Error(await responseError(r));
      setMessage(`Product ${product.name} updated.`); await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not update product."); }
  }
  function onFile(e: ChangeEvent<HTMLInputElement>) { setUploadFile(e.target.files?.[0] ?? null); }

  const navItems: Array<{ id: AdminSection; label: string; icon: typeof LayoutDashboard }> = [
    { id: "discount_usage", label: "Discount usage history", icon: IndianRupee },
    { id: "dashboard", label: "Dashboard & reports", icon: LayoutDashboard },
    { id: "inventory", label: "All inventory", icon: Warehouse },
    { id: "low_stock", label: "Low-stock alerts", icon: AlertTriangle },
    { id: "expiry", label: "Expiry management", icon: ClipboardList },
    { id: "stock_cost", label: "Average stock cost", icon: IndianRupee },
    { id: "stock_import", label: "Bulk stock import", icon: Upload },
    { id: "fast_selling", label: "Fast-selling products", icon: Boxes },
    { id: "product_requests", label: "Product requests", icon: MessageSquareText },
    { id: "products", label: "Manage products & offers", icon: Package },
    { id: "add_product", label: "Add new product", icon: PackagePlus },
    { id: "orders", label: "Orders & tracking", icon: ShoppingCart },
    { id: "feedback", label: "Customer feedback", icon: MessageSquareText },
    { id: "feature_requests", label: "Feature requests", icon: ClipboardList },
    { id: "support", label: "Customer support", icon: LifeBuoy },
  ];
  const money = (value: number | string | null | undefined) => `€${Number(value ?? 0).toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  return <main className="admin-page">
    <header className="admin-header"><label className="language-picker"><span>Language</span><select value={language} onChange={e=>setLanguage(e.target.value as typeof language)}>{languageOptions.map(option=><option key={option.value} value={option.value}>{option.label}</option>)}</select></label><button className="admin-back" onClick={onBack}><ArrowLeft size={17}/> Storefront</button><div><span className="admin-kicker">DESI MASALA · OPERATIONS</span><h1>Admin workspace</h1><p>Manage each part of your store from a dedicated section.</p></div><button className="admin-refresh" onClick={() => void load()}><RefreshCw size={16}/> Refresh</button></header>
    <nav className="admin-nav" aria-label="Admin sections">{navItems.map(item => { const Icon = item.icon; return <button key={item.id} className={activeSection === item.id ? "admin-nav-item active" : "admin-nav-item"} onClick={() => setActiveSection(item.id)}><Icon size={17}/><span>{item.label}</span></button>; })}</nav>
    {error && <div className="admin-alert error">{error}</div>}{message && <div className="admin-alert success">{message}</div>}

    {activeSection === "discount_usage" && <section className="admin-panel"><h2>Discount usage history</h2><p>Promo-code redemptions recorded at checkout. Loyalty discounts are also stored on order rows.</p><div className="admin-table-wrap"><table><thead><tr><th>Date</th><th>Customer</th><th>Promo code</th><th>Discount %</th><th>Discount value</th><th>Order IDs</th></tr></thead><tbody>{discountUsage.map(row=><tr key={row.id}><td>{new Date(row.created_at).toLocaleString()}</td><td>{row.customer_name}<small>{row.email}</small></td><td><strong>{row.promo_code}</strong></td><td>{row.discount_percent}%</td><td>{money(row.discount_amount)}</td><td>{(row.order_ids||[]).map(id=>`#${id}`).join(", ")||"—"}</td></tr>)}</tbody></table>{discountUsage.length===0&&<p className="admin-muted">No promo codes have been redeemed yet.</p>}</div><p className="admin-footnote">Available promo codes are configured in the promo_codes table. EARLYBIRD20 is added by migration 008.</p></section>}

    {activeSection === "dashboard" && <>
      <section className="admin-panel admin-notifications-panel"><div className="admin-notifications-heading"><div><h2>Store notifications</h2><p>New orders and support requests for the admin team.</p></div><div className="admin-notifications-actions"><span>{notifications.filter(n => !n.read_at).length} unread</span><button type="button" onClick={() => void runNotificationCampaigns()}>Check offer alerts</button></div></div>
        {notifications.length === 0 ? <p className="admin-muted">No store notifications yet. New orders and support requests will appear here.</p> : <div className="admin-notification-list">{notifications.slice(0,8).map(n => <article key={n.id} className={n.read_at ? "admin-notification-item read" : "admin-notification-item unread"}><div><strong>{n.title}</strong><p>{n.message}</p><small>{new Date(n.created_at).toLocaleString("de-DE")}</small></div>{!n.read_at && <button type="button" onClick={() => void markNotificationRead(n.id)}>Mark read</button>}</article>)}</div>}
      </section>
      <section className="admin-metrics">
        <article><Boxes/><span>Active products</span><strong>{overview?.products_count ?? "—"}</strong></article>
        <article><ClipboardList/><span>Total order lines</span><strong>{overview?.orders.order_count ?? "—"}</strong></article>
        <article><AlertTriangle/><span>Orders to process</span><strong>{overview?.orders.pending_orders ?? "—"}</strong></article>
        <article><IndianRupee/><span>Paid revenue</span><strong>{money(overview?.orders.paid_revenue)}</strong><small>Only paid orders are counted</small></article>
      </section>
      <section className="admin-chart-grid">
        <article className="admin-panel admin-chart-card"><div className="admin-chart-heading"><div><h2>Daily sales</h2><p>Paid sales for each of the last 30 days.</p></div><span className="admin-chart-tag">30 days</span></div><BarChart rows={(analytics?.daily_sales ?? []).map(x => ({ label: new Date(`${x.day}T12:00:00`).toLocaleDateString("en-GB", { day: "2-digit", month: "short" }), value: Number(x.sales) }))} color="#477c59" money={money}/></article>
        <article className="admin-panel admin-chart-card"><div className="admin-chart-heading"><div><h2>Investment vs sold</h2><p>Stock received cost compared with paid sales by month.</p></div><span className="admin-chart-tag">6 months</span></div><GroupedBarChart rows={(analytics?.monthly_comparison ?? []).map(x => ({ label: new Date(`${x.month}-15T12:00:00`).toLocaleDateString("en-GB", { month: "short", year: "2-digit" }), first: Number(x.investment), second: Number(x.sales) }))} firstLabel="Stock investment" secondLabel="Sales" money={money}/></article>
        <article className="admin-panel admin-chart-card admin-chart-wide"><div className="admin-chart-heading"><div><h2>Profit & loss</h2><p>Monthly paid revenue minus estimated cost of goods sold. Excludes operating expenses, tax and shipping unless recorded separately.</p></div><span className="admin-chart-tag">6 months</span></div><LineChart rows={(analytics?.monthly_profit_loss ?? []).map(x => ({ label: new Date(`${x.month}-15T12:00:00`).toLocaleDateString("en-GB", { month: "short" }), value: Number(x.profit) }))} money={money}/></article>
      </section>
      <p className="admin-footnote">Financial charts use paid, non-cancelled orders. Stock investment is based on received inventory batches. Profit is an estimate based on recorded batch costs, excluding unrecorded operating expenses, tax and shipping.</p>
    </>}

    {activeSection === "inventory" && <section className="admin-panel"><h2><Warehouse size={20}/> Inventory overview</h2><p>Current inventory indicators. Use the dedicated sections in the menu to review low stock, expiry dates, costs, imports and product sales separately.</p><section className="admin-metrics admin-inventory-metrics"><article><Boxes/><span>Products tracked</span><strong>{overview?.products_count ?? "—"}</strong></article><article><AlertTriangle/><span>Low-stock products</span><strong>{overview?.low_stock.length ?? "—"}</strong></article><article><ClipboardList/><span>Expiring batches</span><strong>{overview?.expiring_stock.length ?? "—"}</strong></article><article><IndianRupee/><span>Products with cost data</span><strong>{overview?.average_costs.filter(x => x.weighted_average_cost != null).length ?? "—"}</strong></article></section></section>}

    {activeSection === "low_stock" && <section className="admin-panel"><h2><AlertTriangle size={20}/> Low-stock alerts</h2><p>Products with 10 or fewer units across warehouses.</p>{!overview?.low_stock.length ? <p className="admin-muted">No low-stock products.</p> : <div className="admin-table-wrap"><table><thead><tr><th>Product</th><th>Available quantity</th><th>Alert</th></tr></thead><tbody>{overview.low_stock.map(p => <tr key={p.id}><td>{p.name}</td><td><span className="stock-pill">{p.stock_quantity}</span></td><td><span className="admin-status-warning">Restock recommended</span></td></tr>)}</tbody></table></div>}</section>}

    {activeSection === "expiry" && <section className="admin-panel"><h2><ClipboardList size={20}/> Expiry management</h2><p>Inventory batches expiring within 30 days. Review these products and set an appropriate discount from Products & offers.</p>{!overview?.expiring_stock.length ? <p className="admin-muted">No expiring batches recorded. Add expiry dates during stock import.</p> : <div className="admin-table-wrap"><table><thead><tr><th>Product</th><th>Expiry date</th><th>Quantity remaining</th><th>Unit cost</th><th>Warehouse</th></tr></thead><tbody>{overview.expiring_stock.map(b=><tr key={b.id}><td>{b.name}</td><td>{String(b.expiry_date).slice(0,10)}</td><td>{b.quantity_remaining}</td><td>{money(b.unit_cost)}</td><td>{b.warehouse_name}</td></tr>)}</tbody></table></div>}</section>}

    {activeSection === "stock_cost" && <section className="admin-panel"><h2><IndianRupee size={20}/> Weighted average stock cost</h2><p>Calculated from remaining batch quantities and recorded unit costs. This is inventory cost, not the selling price.</p><div className="admin-table-wrap"><table><thead><tr><th>Product</th><th>Batch units remaining</th><th>Weighted average cost</th></tr></thead><tbody>{(overview?.average_costs ?? []).map(p=><tr key={p.id}><td>{p.name}</td><td>{p.batch_quantity}</td><td>{p.weighted_average_cost==null?"Not recorded":money(p.weighted_average_cost)}</td></tr>)}</tbody></table></div></section>}

    {activeSection === "stock_import" && <section className="admin-panel"><h2><Upload size={20}/> Bulk stock import</h2><p>Upload a CSV file. Quantities are added to inventory and each row records batch cost and optional expiry date.</p><p className="admin-code">product_id,product_name,warehouse_id,quantity,unit_cost,new_price,expiry_date,supplier_reference,brand,category</p><p><a href="/stock-import-template.csv" download>Download sample stock CSV</a></p><div className="admin-upload"><input type="file" accept=".csv,text/csv" onChange={onFile}/><button className="admin-primary" disabled={!uploadFile||busy} onClick={() => void importStock()}>{busy ? "Importing…" : "Import stock"}</button></div><small>For Excel, save the worksheet as CSV first. Test with a copy of your file before uploading.</small></section>}

    {activeSection === "fast_selling" && <section className="admin-panel"><h2><Boxes size={20}/> Fast-selling products</h2><p>Units sold in the last 30 days, excluding cancelled orders.</p><div className="admin-table-wrap"><table><thead><tr><th>Product</th><th>Units sold</th></tr></thead><tbody>{(overview?.fast_selling ?? []).map(p=><tr key={p.id}><td>{p.name}</td><td>{p.units_sold}</td></tr>)}</tbody></table></div>{!overview?.fast_selling.length && <p className="admin-muted">No sales data is available yet.</p>}</section>}

    {activeSection === "product_requests" && <section className="admin-panel"><h2><MessageSquareText size={20}/> Most requested products</h2><p>Outstanding back-in-stock requests from customers.</p><div className="admin-table-wrap"><table><thead><tr><th>Product</th><th>Requests</th><th>Current stock</th></tr></thead><tbody>{(overview?.most_requested ?? []).map(p=><tr key={p.id}><td>{p.name}</td><td>{p.request_count}</td><td>{p.stock_quantity}</td></tr>)}</tbody></table></div>{!overview?.most_requested.length && <p className="admin-muted">No product requests recorded yet.</p>}</section>}

    {activeSection === "products" && <>
      <section className="admin-panel"><h2>Products, discounts and offers</h2><p>Update prices, discounts, featured status, new arrivals, and storefront visibility.</p><div className="admin-table-wrap"><table><thead><tr><th>Product</th><th>Stock</th><th>Price (€)</th><th>Discount %</th><th>Expiry offer</th><th>Featured</th><th>New</th><th>Active</th><th>Save</th></tr></thead><tbody>{products.map(p=><tr key={p.id}><td>{p.name}<small>{p.category}</small></td><td>{p.stock_quantity}</td><td><input aria-label={`Price for ${p.name}`} className="admin-inline-input" type="number" min="0" step="0.01" value={p.price} onChange={e=>setProducts(prev=>prev.map(x=>x.id===p.id?{...x,price:e.target.value}:x))}/></td><td><input aria-label={`Discount for ${p.name}`} className="admin-inline-input" type="number" min="0" max="100" step="1" value={p.discount_percent} onChange={e=>setProducts(prev=>prev.map(x=>x.id===p.id?{...x,discount_percent:e.target.value}:x))}/></td><td>{Number(p.expiry_discount_percent||0)>0?`${p.expiry_discount_percent}% until ${p.expiry_discount_until||"—"}`:"—"}</td><td><input aria-label={`Feature ${p.name}`} type="checkbox" checked={p.is_featured} onChange={e=>setProducts(prev=>prev.map(x=>x.id===p.id?{...x,is_featured:e.target.checked}:x))}/></td><td><input aria-label={`New arrival ${p.name}`} type="checkbox" checked={p.is_new_arrival} onChange={e=>setProducts(prev=>prev.map(x=>x.id===p.id?{...x,is_new_arrival:e.target.checked}:x))}/></td><td><input aria-label={`Active ${p.name}`} type="checkbox" checked={p.active} onChange={e=>setProducts(prev=>prev.map(x=>x.id===p.id?{...x,active:e.target.checked}:x))}/></td><td><button className="admin-primary admin-save-small" onClick={()=>void saveProduct(p)}>Save</button></td></tr>)}</tbody></table></div></section>
    </>}

    {activeSection === "add_product" && <>
      <section className="admin-panel"><h2><PackagePlus size={20}/> Add product</h2><form className="admin-product-form" onSubmit={createProduct}><label>Product name<input required value={newProduct.name} onChange={e=>setNewProduct({...newProduct,name:e.target.value})}/></label><label>Price (€)<input type="number" min="0" step="0.01" required value={newProduct.price} onChange={e=>setNewProduct({...newProduct,price:e.target.value})}/></label><label>Brand<input value={newProduct.brand} onChange={e=>setNewProduct({...newProduct,brand:e.target.value})}/></label><label>Category<select value={newProduct.category} onChange={e=>setNewProduct({...newProduct,category:e.target.value})}>{["Rice & Grains","Lentils & Beans","Spices","Fresh Produce","Pickles & Sauces","Tea & Drinks","Other Groceries"].map(c=><option key={c}>{c}</option>)}</select></label><label>Discount %<input type="number" min="0" max="100" step="1" value={newProduct.discount_percent} onChange={e=>setNewProduct({...newProduct,discount_percent:e.target.value})}/></label><label>Description<input value={newProduct.description} onChange={e=>setNewProduct({...newProduct,description:e.target.value})}/></label><label className="admin-check"><input type="checkbox" checked={newProduct.is_featured} onChange={e=>setNewProduct({...newProduct,is_featured:e.target.checked})}/> Featured offer</label><label className="admin-check"><input type="checkbox" checked={newProduct.is_new_arrival} onChange={e=>setNewProduct({...newProduct,is_new_arrival:e.target.checked})}/> New arrival</label><button className="admin-primary" disabled={busy}>{busy ? "Saving…" : "Create product"}</button></form></section>
    </>}

    {activeSection === "orders" && <section className="admin-panel"><h2>Order history & shipment tracking</h2><p>Update fulfilment status and enter carrier tracking details. Customers can see the timeline in their account.</p><div className="admin-table-wrap"><table><thead><tr><th>Order</th><th>Customer</th><th>Product</th><th>Qty</th><th>Amount</th><th>Payment</th><th>Status</th><th>Carrier</th><th>Tracking number</th><th>Tracking URL</th><th>ETA</th><th>Save shipment</th></tr></thead><tbody>{orders.map(o=>{const draft=trackingDraft[o.id]||{carrier:o.carrier||"DHL",tracking_number:o.tracking_number||"",tracking_url:o.tracking_url||"",estimated_delivery:o.estimated_delivery?String(o.estimated_delivery).slice(0,10):""};return <tr key={o.id}><td>#{o.id}<small>{new Date(o.created_at).toLocaleString()}</small></td><td>{o.customer_name}<small>{o.email}</small></td><td>{o.product_name}</td><td>{o.quantity}</td><td>{money(o.amount)}</td><td>{o.payment_status}</td><td><select aria-label={`Status for order ${o.id}`} value={o.status} onChange={e=>void updateStatus(o.id,e.target.value)}>{["PLACED","CONFIRMED","PACKING","SHIPPED","DELIVERED","CANCELLED"].map(st=><option key={st}>{st}</option>)}</select><small>Current: {o.status}</small></td><td><select aria-label={`Carrier for order ${o.id}`} value={draft.carrier} onChange={e=>setTrackingDraft(prev=>({...prev,[o.id]:{...draft,carrier:e.target.value}}))}>{["DHL","DPD","Hermes","GLS","UPS","Deutsche Post","Other"].map(c=><option key={c}>{c}</option>)}</select></td><td><input aria-label={`Tracking number for order ${o.id}`} className="admin-inline-input" value={draft.tracking_number} onChange={e=>setTrackingDraft(prev=>({...prev,[o.id]:{...draft,tracking_number:e.target.value}}))} placeholder="Tracking no."/></td><td><input aria-label={`Tracking URL for order ${o.id}`} className="admin-inline-input" value={draft.tracking_url} onChange={e=>setTrackingDraft(prev=>({...prev,[o.id]:{...draft,tracking_url:e.target.value}}))} placeholder="https://…"/></td><td><input aria-label={`Estimated delivery for order ${o.id}`} type="date" className="admin-inline-input" value={draft.estimated_delivery} onChange={e=>setTrackingDraft(prev=>({...prev,[o.id]:{...draft,estimated_delivery:e.target.value}}))}/></td><td><button className="admin-primary admin-save-small" onClick={()=>void updateStatus(o.id,o.status,{carrier:draft.carrier||undefined,tracking_number:draft.tracking_number||undefined,tracking_url:draft.tracking_url||undefined,estimated_delivery:draft.estimated_delivery||undefined})}>Save tracking</button>{o.payment_status === "PENDING" && o.status !== "CANCELLED" && <button className="admin-save-small" onClick={()=>void confirmManualPayment(o.id)}>Confirm payment received</button>}</td></tr>})}</tbody></table>{orders.length===0&&<p className="admin-muted">No orders found.</p>}</div><p className="admin-footnote">Only confirm manual payment after verifying the transfer in your bank account.</p></section>}
    {activeSection === "feedback" && <AdminEngagement token={token} mode="feedback"/>}
    {activeSection === "feature_requests" && <AdminEngagement token={token} mode="requests"/>}
    {activeSection === "support" && <AdminSupportPanel token={token}/>}
  </main>;

}


function BarChart({ rows, color, money }: { rows: Array<{label:string;value:number}>; color:string; money:(n:number)=>string }) {
  const width=760, height=260, left=48, right=14, top=18, bottom=42, plotW=width-left-right, plotH=height-top-bottom;
  const max=Math.max(1,...rows.map(r=>r.value)); const step=rows.length?plotW/rows.length:plotW; const barW=Math.max(3,step*.62);
  return <div className="admin-svg-scroll"><svg className="admin-chart-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Daily paid sales bar chart">
    {[0,.25,.5,.75,1].map(t=><g key={t}><line x1={left} x2={width-right} y1={top+plotH*(1-t)} y2={top+plotH*(1-t)} stroke="#e8eee8"/><text x={left-8} y={top+plotH*(1-t)+4} textAnchor="end" fill="#718074" fontSize="10">{Math.round(max*t)}</text></g>)}
    {rows.map((r,i)=>{const h=r.value/max*plotH; return <g key={r.label}><title>{`${r.label}: ${money(r.value)}`}</title><rect x={left+i*step+(step-barW)/2} y={top+plotH-h} width={barW} height={Math.max(0,h)} rx="3" fill={color}/>{(rows.length<=15 || i%3===0 || i===rows.length-1)&&<text x={left+i*step+step/2} y={height-18} textAnchor="middle" fill="#718074" fontSize="10">{r.label}</text>}</g>})}
  </svg></div>;
}
function GroupedBarChart({ rows, firstLabel, secondLabel, money }: { rows:Array<{label:string;first:number;second:number}>; firstLabel:string; secondLabel:string; money:(n:number)=>string }) {
  const width=760,height=270,left=52,right=14,top=18,bottom=46,plotW=width-left-right,plotH=height-top-bottom,max=Math.max(1,...rows.flatMap(r=>[r.first,r.second])),step=rows.length?plotW/rows.length:plotW,bw=Math.max(4,step*.28);
  return <><div className="admin-chart-legend"><span><i className="legend-investment"/>{firstLabel}</span><span><i className="legend-sales"/>{secondLabel}</span></div><div className="admin-svg-scroll"><svg className="admin-chart-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Monthly stock investment versus sales grouped bar chart">{[0,.25,.5,.75,1].map(t=><g key={t}><line x1={left} x2={width-right} y1={top+plotH*(1-t)} y2={top+plotH*(1-t)} stroke="#e8eee8"/><text x={left-8} y={top+plotH*(1-t)+4} textAnchor="end" fill="#718074" fontSize="10">{Math.round(max*t)}</text></g>)}{rows.map((r,i)=>{const x=left+i*step+step/2,h1=r.first/max*plotH,h2=r.second/max*plotH;return <g key={r.label}><title>{`${r.label}: investment ${money(r.first)}, sales ${money(r.second)}`}</title><rect x={x-bw-2} y={top+plotH-h1} width={bw} height={h1} rx="3" fill="#d6a34b"/><rect x={x+2} y={top+plotH-h2} width={bw} height={h2} rx="3" fill="#477c59"/><text x={x} y={height-18} textAnchor="middle" fill="#718074" fontSize="11">{r.label}</text></g>})}</svg></div></>;
}
function LineChart({ rows, money }: { rows:Array<{label:string;value:number}>; money:(n:number)=>string }) {
  const width=760,height=260,left=58,right=16,top=18,bottom=42,plotW=width-left-right,plotH=height-top-bottom,min=Math.min(0,...rows.map(r=>r.value)),max=Math.max(1,...rows.map(r=>r.value)),range=Math.max(1,max-min),xAt=(i:number)=>left+(rows.length<=1?plotW/2:i*plotW/(rows.length-1)),yAt=(v:number)=>top+(max-v)/range*plotH,points=rows.map((r,i)=>`${xAt(i)},${yAt(r.value)}`).join(" ");
  return <div className="admin-svg-scroll"><svg className="admin-chart-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Monthly profit and loss line chart">{[0,.25,.5,.75,1].map(t=>{const v=max-range*t;return <g key={t}><line x1={left} x2={width-right} y1={top+plotH*t} y2={top+plotH*t} stroke="#e8eee8"/><text x={left-8} y={top+plotH*t+4} textAnchor="end" fill="#718074" fontSize="10">{Math.round(v)}</text></g>})}<line x1={left} x2={width-right} y1={yAt(0)} y2={yAt(0)} stroke="#aeb9ad" strokeDasharray="4 4"/><polyline points={points} fill="none" stroke="#477c59" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round"/>{rows.map((r,i)=><g key={r.label}><title>{`${r.label}: ${money(r.value)}`}</title><circle cx={xAt(i)} cy={yAt(r.value)} r="4.5" fill="#477c59" stroke="white" strokeWidth="2"/><text x={xAt(i)} y={height-18} textAnchor="middle" fill="#718074" fontSize="11">{r.label}</text></g>)}</svg></div>;
}
