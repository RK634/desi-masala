
import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  ArrowLeft,
  MapPin,
  ClipboardList,
  Bell,
  CreditCard,
  Plus,
  Truck,
  PackageCheck,
  XCircle,
  ExternalLink,
  UserRound,
  MessageSquare,
  Lightbulb,
} from "lucide-react";
import { API_URL, authFetch } from "./commerceApi";
import "./CustomerDashboard.css";
import { lookupCity } from "./postcodeLookup";
import {useLanguage,languageOptions,type Language,} from "./LanguageContext";

type LanguageOption = {
  value: Language
  label: string;
};
import SupportPanel from "./SupportPanel";
import { CustomerEngagement } from "./EngagementPanels";

type Address = {
  id: number;
  label: string;
  recipient_name: string;
  address_line1: string;
  address_line2?: string | null;
  postal_code: string;
  city: string;
  country: string;
  is_default: boolean;
};

type TrackingEvent = {
  status: string;
  note?: string | null;
  created_at: string;
};

type Order = {
  id: number;
  product_name: string;
  quantity: number;
  amount: number | string;
  status: string;
  payment_status: string;
  created_at: string;
  carrier?: string | null;
  tracking_number?: string | null;
  tracking_url?: string | null;
  estimated_delivery?: string | null;
  shipped_at?: string | null;
  delivered_at?: string | null;
  tracking_history?: TrackingEvent[];
};

type PaymentMethod = {
  id: number;
  provider: string;
  brand?: string | null;
  last4?: string | null;
  exp_month?: number | null;
  exp_year?: number | null;
  is_default: boolean;
};

type Preferences = {
  order_updates: boolean;
  back_in_stock: boolean;
  new_products: boolean;
  abandoned_cart_reminders: boolean;
  marketing_emails: boolean;
  discount_alerts: boolean;
  birthday_offers: boolean;
  expiry_alerts: boolean;
  whatsapp_enabled: boolean;
  whatsapp_number: string;
  whatsapp_order_updates: boolean;
  whatsapp_marketing: boolean;
};
type CustomerNotification = { id: number; kind: string; title: string; message: string; read_at: string | null; created_at: string; related_product_id?: number | null };

type AccountSection =
  | "profile"
  | "addresses"
  | "payments"
  | "orders"
  | "requests"
  | "feedback"
  | "notifications";

const defaultPreferences: Preferences = {
  order_updates: true,
  back_in_stock: true,
  new_products: false,
  abandoned_cart_reminders: false,
  marketing_emails: false,
  discount_alerts: false,
  birthday_offers: false,
  expiry_alerts: false,
  whatsapp_enabled: false,
  whatsapp_number: "",
  whatsapp_order_updates: true,
  whatsapp_marketing: false,
};

const accountSections: {
  id: AccountSection;
  label: string;
  description: string;
  icon: typeof UserRound;
}[] = [
  {
    id: "profile",
    label: "My Profile",
    description: "Personal details",
    icon: UserRound,
  },
  {
    id: "addresses",
    label: "Addresses",
    description: "Delivery addresses",
    icon: MapPin,
  },
  {
    id: "payments",
    label: "Payment Information",
    description: "Payment details",
    icon: CreditCard,
  },
  {
    id: "orders",
    label: "Orders & Tracking",
    description: "Order history and delivery",
    icon: ClipboardList,
  },
  {
    id: "requests",
    label: "Product Requests",
    description: "Suggest products",
    icon: Lightbulb,
  },
  {
    id: "feedback",
    label: "Feedback & Support",
    description: "Feedback and assistance",
    icon: MessageSquare,
  },
  {
    id: "notifications",
    label: "Notifications",
    description: "Manage preferences",
    icon: Bell,
  },
];

export default function CustomerDashboard({
  token,
  onBack,
}: {
  token: string;
  onBack: () => void;
}) {
  const [activeSection, setActiveSection] =
    useState<AccountSection>("addresses");

  const [addresses, setAddresses] = useState<Address[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [methods, setMethods] = useState<PaymentMethod[]>([]);
  const [preferences, setPreferences] =
    useState<Preferences>(defaultPreferences);
  const [notifications, setNotifications] = useState<CustomerNotification[]>([]);

  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [trackingOpen, setTrackingOpen] = useState<number | null>(null);

  const { language, setLanguage } = useLanguage();
  const [form, setForm] = useState({
    label: "Home",
    recipient_name: "",
    phone: "",
    address_line1: "",
    address_line2: "",
    postal_code: "",
    city: "",
    country: "Germany",
    is_default: true,
  });

  useEffect(() => { let cancelled=false; const timer=window.setTimeout(async()=>{ if(form.postal_code.trim().length<3)return; const found=await lookupCity(form.postal_code,form.country); if(!cancelled&&found)setForm(current=>({...current,city:found})); },350); return ()=>{cancelled=true;window.clearTimeout(timer);}; },[form.postal_code,form.country]);

  async function err(r: Response) {
    try {
      const body = await r.json();
      return body.detail || `Request failed (${r.status})`;
    } catch {
      return `Request failed (${r.status})`;
    }
  }

  const load = useCallback(async () => {
    try {
      setError("");

      const [a, o, p, n, notificationResponse] = await Promise.all([
        authFetch(`${API_URL}/commerce/customer/addresses`, token),
        authFetch(`${API_URL}/commerce/customer/orders`, token),
        authFetch(`${API_URL}/commerce/customer/payment-methods`, token),
        authFetch(`${API_URL}/commerce/customer/notification-preferences`, token),
        authFetch(`${API_URL}/commerce/customer/notifications`, token),
      ]);

      for (const response of [a, o, p, n, notificationResponse]) {
        if (!response.ok) {
          throw new Error(await err(response));
        }
      }

      setAddresses(await a.json());
      setOrders(await o.json());
      setMethods(await p.json());
      const preferenceData = await n.json();
      setPreferences({ ...defaultPreferences, ...preferenceData, whatsapp_number: preferenceData.whatsapp_number || "" });
      setNotifications(await notificationResponse.json());
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not load account data."
      );
    }
  }, [token]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 0);

    return () => window.clearTimeout(timer);
  }, [load]);

  async function addAddress(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");

    try {
      const response = await authFetch(
        `${API_URL}/commerce/customer/addresses`,
        token,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(form),
        }
      );

      if (!response.ok) {
        throw new Error(await err(response));
      }

      setMessage("Delivery address saved.");
      setForm({
        ...form,
        recipient_name: "",
        phone: "",
        address_line1: "",
        address_line2: "",
        postal_code: "",
      });

      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save address.");
    } finally {
      setBusy(false);
    }
  }

  async function cancelOrder(orderId: number) {
    if (
      !window.confirm(
        `Cancel order #${orderId}? This is only possible before packing or shipping.`
      )
    ) {
      return;
    }

    setError("");
    setMessage("");

    try {
      const response = await authFetch(
        `${API_URL}/commerce/customer/orders/${orderId}/cancel`,
        token,
        { method: "POST" }
      );

      if (!response.ok) {
        throw new Error(await err(response));
      }

      setMessage(`Order #${orderId} cancelled.`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not cancel order.");
    }
  }

  async function markNotificationRead(id: number) {
    try {
      const response = await authFetch(`${API_URL}/commerce/customer/notifications/${id}/read`, token, { method: "PATCH" });
      if (!response.ok) throw new Error(await err(response));
      setNotifications(current => current.map(item => item.id === id ? { ...item, read_at: new Date().toISOString() } : item));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update notification.");
    }
  }

  async function savePreferences(next: Preferences) {
    const previous = preferences;
    setPreferences(next);
    setError("");
    setMessage("");

    try {
      const response = await authFetch(
        `${API_URL}/commerce/customer/notification-preferences`,
        token,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(next),
        }
      );

      if (!response.ok) {
        throw new Error(await err(response));
      }

      setMessage("Notification preferences saved.");
    } catch (e) {
      setPreferences(previous);
      setError(
        e instanceof Error ? e.message : "Could not save preferences."
      );
    }
  }

  function selectSection(section: AccountSection) {
    setActiveSection(section);
    setError("");
    setMessage("");
  }

  return (
    <main className="customer-account">
      <header className="customer-account-header"><label className="language-picker"><span>Language</span><select value={language} onChange={e=>setLanguage(e.target.value as typeof language)}>{languageOptions.map((option: LanguageOption) => (<option key={option.value} value={option.value}>{option.label}</option>))}</select></label>
        <button type="button" onClick={onBack}>
          <ArrowLeft size={17} />
          Back to store
        </button>

        <div>
          <span>DESI MASALA · YOUR ACCOUNT</span>
          <h1>Your account</h1>
          <p>Manage your profile, addresses, payments and orders.</p>
        </div>
      </header>

      {error && (
        <div className="customer-message error" role="alert">
          {error}
        </div>
      )}

      {message && (
        <div className="customer-message success" role="status">
          {message}
        </div>
      )}

      <div className="customer-layout">
        <aside className="customer-sidebar">
          <h2>Account settings</h2>

          <nav aria-label="Account sections">
            {accountSections.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                className={`customer-nav-item ${
                  activeSection === id ? "active" : ""
                }`}
                onClick={() => selectSection(id)}
                aria-current={activeSection === id ? "page" : undefined}
              >
                <Icon size={18} />
                <span>{label}</span>
              </button>
            ))}
          </nav>
        </aside>

        <div className="customer-section-content">
          {activeSection === "profile" && (
            <section className="customer-panel">
              <h2>
                <UserRound />
                My Profile
              </h2>
              <p className="customer-muted">
                Your personal information and account settings.
              </p>
              <p>
                Profile editing should be connected to your existing profile
                API before adding editable fields here.
              </p>
            </section>
          )}

          {activeSection === "addresses" && (
            <section className="customer-panel">
              <h2>
                <MapPin />
                Delivery addresses
              </h2>

              {addresses.map((address) => (
                <article className="saved-address" key={address.id}>
                  <strong>
                    {address.label}
                    {address.is_default ? " · Default" : ""}
                  </strong>
                  <span>{address.recipient_name}</span>
                  <span>
                    {address.address_line1}
                    {address.address_line2
                      ? `, ${address.address_line2}`
                      : ""}
                  </span>
                  <span>
                    {address.postal_code} {address.city}, {address.country}
                  </span>
                </article>
              ))}

              {addresses.length === 0 && (
                <p className="customer-muted">No saved address yet.</p>
              )}

              <form className="address-form" onSubmit={addAddress}>
                <h3>
                  <Plus size={17} />
                  Add delivery address
                </h3>

                <label>
                  Label
                  <input
                    value={form.label}
                    onChange={(e) =>
                      setForm({ ...form, label: e.target.value })
                    }
                    required
                  />
                </label>

                <label>
                  Recipient name
                  <input
                    value={form.recipient_name}
                    onChange={(e) =>
                      setForm({ ...form, recipient_name: e.target.value })
                    }
                    required
                  />
                </label>

                <label>
                  Phone
                  <input
                    value={form.phone}
                    onChange={(e) =>
                      setForm({ ...form, phone: e.target.value })
                    }
                  />
                </label>

                <label>
                  Address line
                  <input
                    value={form.address_line1}
                    onChange={(e) =>
                      setForm({ ...form, address_line1: e.target.value })
                    }
                    required
                  />
                </label>

                <label>
                  Apartment / additional details
                  <input
                    value={form.address_line2}
                    onChange={(e) =>
                      setForm({ ...form, address_line2: e.target.value })
                    }
                  />
                </label>

                <div className="address-two">
                  <label>
                    Postcode
                    <input
                      value={form.postal_code}
                      onChange={(e) =>
                        setForm({ ...form, postal_code: e.target.value })
                      }
                      required
                    />
                  </label>

                  <label>
                    City
                    <input
                      value={form.city}
                      onChange={(e) =>
                        setForm({ ...form, city: e.target.value })
                      }
                      required
                    />
                  </label>
                </div>

                <label className="address-default">
                  <input
                    type="checkbox"
                    checked={form.is_default}
                    onChange={(e) =>
                      setForm({ ...form, is_default: e.target.checked })
                    }
                  />
                  Set as default address
                </label>

                <button disabled={busy}>
                  {busy ? "Saving…" : "Save address"}
                </button>
              </form>
            </section>
          )}

          {activeSection === "payments" && (
            <section className="customer-panel">
              <h2>
                <CreditCard />
                Payment Information
              </h2>

              {methods.length === 0 ? (
                <p className="customer-muted">
                  Saved online payment methods are not used while manual
                  payment is enabled.
                </p>
              ) : (
                methods.map((method) => (
                  <article className="saved-address" key={method.id}>
                    <strong>
                      {method.brand || method.provider} ••••{" "}
                      {method.last4 || "----"}
                      {method.is_default ? " · Default" : ""}
                    </strong>
                    <span>
                      Expires {method.exp_month || "—"}/
                      {method.exp_year || "—"}
                    </span>
                  </article>
                ))
              )}

              <p className="customer-security-note">
                Manual payment is enabled for now. The store will update the
                order once payment has been received. Online payment can be
                enabled later.
              </p>
            </section>
          )}

          {activeSection === "orders" && (
            <section className="customer-panel">
              <h2>
                <ClipboardList />
                Orders & tracking
              </h2>

              {orders.length === 0 ? (
                <p className="customer-muted">
                  Your order history will appear here.
                </p>
              ) : (
                <div className="customer-order-list">
                  {orders.map((order) => (
                    <article className="tracked-order" key={order.id}>
                      <div className="tracked-order-summary">
                        <strong>
                          {order.product_name} × {order.quantity}
                        </strong>
                        <small>
                          Order #{order.id} ·{" "}
                          {new Date(order.created_at).toLocaleDateString(
                            "de-DE"
                          )}
                        </small>
                        <span
                          className={`order-status status-${order.status.toLowerCase()}`}
                        >
                          {order.status.replaceAll("_", " ")}
                        </span>
                      </div>

                      <div className="tracked-order-total">
                        <strong>€{Number(order.amount).toFixed(2)}</strong>
                        <small>Payment {order.payment_status}</small>

                        {order.payment_status === "PENDING" &&
                          order.status !== "CANCELLED" && (
                            <small className="manual-payment-note">
                              Manual payment · awaiting store confirmation
                            </small>
                          )}

                        <button
                          className="track-button"
                          onClick={() =>
                            setTrackingOpen(
                              trackingOpen === order.id ? null : order.id
                            )
                          }
                        >
                          <Truck size={15} />
                          {trackingOpen === order.id
                            ? "Hide tracking"
                            : "Track order"}
                        </button>

                        {["PLACED", "CONFIRMED"].includes(order.status) && (
                          <button
                            className="cancel-order-button"
                            onClick={() => void cancelOrder(order.id)}
                          >
                            <XCircle size={14} />
                            Cancel
                          </button>
                        )}
                      </div>

                      {trackingOpen === order.id && (
                        <div className="order-tracking-panel">
                          <div className="tracking-topline">
                            <Truck size={18} />
                            <strong>
                              {order.status === "DELIVERED"
                                ? "Delivered"
                                : order.status === "CANCELLED"
                                  ? "Order cancelled"
                                  : order.status === "SHIPPED"
                                    ? "On the way"
                                    : "Order progress"}
                            </strong>
                          </div>

                          {order.estimated_delivery && (
                            <p>
                              <strong>Estimated delivery:</strong>{" "}
                              {new Date(
                                `${order.estimated_delivery}T12:00:00`
                              ).toLocaleDateString("de-DE")}
                            </p>
                          )}

                          {order.carrier && (
                            <p>
                              <strong>Carrier:</strong> {order.carrier}
                            </p>
                          )}

                          {order.tracking_number && (
                            <p>
                              <strong>Tracking number:</strong>{" "}
                              <code>{order.tracking_number}</code>
                            </p>
                          )}

                          {order.tracking_url && (
                            <a
                              className="carrier-link"
                              href={order.tracking_url}
                              target="_blank"
                              rel="noreferrer"
                            >
                              Track on carrier website
                              <ExternalLink size={14} />
                            </a>
                          )}

                          {!order.tracking_number &&
                            order.status !== "DELIVERED" &&
                            order.status !== "CANCELLED" && (
                              <p className="customer-muted">
                                Your tracking number will appear here after
                                the store dispatches your order.
                              </p>
                            )}

                          <ol className="tracking-timeline">
                            {(
                              order.tracking_history || [
                                {
                                  status: order.status,
                                  note: "Current status",
                                  created_at: order.created_at,
                                },
                              ]
                            ).map((event, index) => (
                              <li
                                key={`${event.status}-${event.created_at}-${index}`}
                              >
                                <span className="tracking-dot">
                                  <PackageCheck size={13} />
                                </span>
                                <div>
                                  <strong>
                                    {event.status.replaceAll("_", " ")}
                                  </strong>
                                  <small>
                                    {new Date(
                                      event.created_at
                                    ).toLocaleString("de-DE")}
                                  </small>
                                  {event.note && <p>{event.note}</p>}
                                </div>
                              </li>
                            ))}
                          </ol>
                        </div>
                      )}
                    </article>
                  ))}
                </div>
              )}
            </section>
          )}

          {activeSection === "requests" && (
            <section className="customer-panel">
              <h2>
                <Lightbulb />
                Product Requests
              </h2>
              <p className="customer-muted">
                Suggest products you would like Desi Masala to stock.
              </p>
              <CustomerEngagement token={token} />
            </section>
          )}

          {activeSection === "feedback" && (
            <section className="customer-panel">
              <h2>
                <MessageSquare />
                Feedback & Support
              </h2>
              <CustomerEngagement token={token} />
              <SupportPanel token={token} />
            </section>
          )}

          {activeSection === "notifications" && (
            <section className="customer-panel customer-notification-settings">
              <h2><Bell /> Notification preferences</h2>
              <p className="customer-muted">Order updates are transactional. Offers, birthday messages and expiry-related promotions are optional marketing alerts.</p>
              {([
                ["order_updates", "Order status updates"],
                ["back_in_stock", "Back-in-stock alerts"],
                ["new_products", "New product alerts"],
                ["abandoned_cart_reminders", "Unfinished cart reminders"],
                ["marketing_emails", "Marketing emails"],
                ["discount_alerts", "Discount and offer alerts"],
                ["birthday_offers", "Birthday offers"],
                ["expiry_alerts", "Expiry-related product offers"],
              ] as const).map(([key, label]) => (
                <label className="notification-option" key={key}><span>{label}</span><input type="checkbox" checked={preferences[key]} onChange={e => void savePreferences({ ...preferences, [key]: e.target.checked })} /></label>
              ))}
              <div className="customer-whatsapp-settings">
                <h3>WhatsApp notifications</h3>
                <p className="customer-muted">WhatsApp is optional and stays inactive until you enable it and the store configures its WhatsApp Cloud API connection. Use an international number, for example +4915112345678.</p>
                <label className="customer-whatsapp-number">WhatsApp number<input type="tel" value={preferences.whatsapp_number} onChange={e => setPreferences(current => ({ ...current, whatsapp_number: e.target.value }))} onBlur={() => void savePreferences(preferences)} placeholder="+49…" autoComplete="tel" /></label>
                {([
                  ["whatsapp_enabled", "Enable WhatsApp notifications"],
                  ["whatsapp_order_updates", "Order and payment updates on WhatsApp"],
                  ["whatsapp_marketing", "Offers and birthday/expiry messages on WhatsApp"],
                ] as const).map(([key, label]) => <label className="notification-option" key={key}><span>{label}</span><input type="checkbox" checked={preferences[key]} onChange={e => void savePreferences({ ...preferences, [key]: e.target.checked })} /></label>)}
                <p className="customer-security-note">Marketing messages require both your marketing opt-in and the relevant notification preference. You can turn WhatsApp off here at any time.</p>
              </div>
              <div className="customer-notification-history"><div className="customer-notification-history-heading"><h3>Notification history</h3><span>{notifications.filter(n => !n.read_at).length} unread</span></div>
                {notifications.length === 0 ? <p className="customer-muted">Your order, payment, support and offer notifications will appear here.</p> : notifications.map(item => <article className={item.read_at ? "customer-notification-item read" : "customer-notification-item unread"} key={item.id}><div><strong>{item.title}</strong><p>{item.message}</p><small>{new Date(item.created_at).toLocaleString("de-DE")}</small></div>{!item.read_at && <button type="button" onClick={() => void markNotificationRead(item.id)}>Mark read</button>}</article>)}
              </div>
            </section>
          )}
        </div>
      </div>
    </main>
  );
}
