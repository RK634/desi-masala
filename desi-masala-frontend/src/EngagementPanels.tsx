
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Heart, MessageSquareText, Send } from "lucide-react";
import { API_URL, authFetch } from "./commerceApi";

type EngagementMode = "feedback" | "requests";

type Feedback = {
  id: number;
  customer_name?: string;
  email?: string;
  feedback_type: string;
  rating: number | null;
  subject: string;
  message: string;
  status: string;
  admin_response?: string | null;
  created_at: string;
};

type Notification = {
  id: number;
  kind: string;
  title: string;
  message: string;
  created_at: string;
  read_at?: string | null;
};

async function errorText(response: Response): Promise<string> {
  try {
    const data = await response.json();

    if (typeof data.detail === "string") return data.detail;

    if (Array.isArray(data.detail)) {
      return data.detail
        .map((item: { msg?: string }) => item.msg ?? JSON.stringify(item))
        .join(", ");
    }

    return data.detail
      ? JSON.stringify(data.detail)
      : `Request failed (${response.status})`;
  } catch {
    return `Request failed (${response.status})`;
  }
}

function formatDate(value: string) {
  return new Date(value).toLocaleString("de-DE");
}

// CUSTOMER: separate feedback and product requests using the mode prop.
export function CustomerEngagement({
  token,
  mode = "feedback",
}: {
  token: string;
  mode?: EngagementMode;
}) {
  const [items, setItems] = useState<Feedback[]>([]);
  const [alerts, setAlerts] = useState<Notification[]>([]);
  const [type, setType] = useState("GENERAL");
  const [rating, setRating] = useState("5");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const isRequest = mode === "requests";

  const load = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const response = await authFetch(
        `${API_URL}/engagement/feedback`,
        token,
      );

      if (!response.ok) throw new Error(await errorText(response));

      const data: Feedback[] = await response.json();
      setItems(data);

      if (!isRequest) {
        const notificationsResponse = await authFetch(
          `${API_URL}/commerce/customer/notifications`,
          token,
        );

        if (!notificationsResponse.ok) {
          throw new Error(await errorText(notificationsResponse));
        }

        setAlerts(await notificationsResponse.json());
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not load information.",
      );
    } finally {
      setLoading(false);
    }
  }, [token, isRequest]);

  useEffect(() => {
    void load();
  }, [load]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");

    try {
      const response = await authFetch(
        `${API_URL}/engagement/feedback`,
        token,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            feedback_type: isRequest ? "FEATURE_REQUEST" : type,
            rating: isRequest ? null : Number(rating),
            subject: subject.trim(),
            message: message.trim(),
          }),
        },
      );

      if (!response.ok) throw new Error(await errorText(response));

      setSubject("");
      setMessage("");
      setNotice(
        isRequest
          ? "Your product request has been submitted."
          : "Thank you! Your feedback has been submitted.",
      );

      await load();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not submit information.",
      );
    }
  }

  const visibleItems = items.filter((item) =>
    isRequest
      ? item.feedback_type === "FEATURE_REQUEST"
      : item.feedback_type !== "FEATURE_REQUEST",
  );

  return (
    <div className={`engagement-panel engagement-${mode}`}>
      {!isRequest && (
        <section className="customer-panel">
          <h2><Heart size={20} /> Alerts &amp; offers</h2>

          {loading ? (
            <p className="customer-muted">Loading alerts...</p>
          ) : alerts.length === 0 ? (
            <p className="customer-muted">
              No alerts or offers are available yet.
            </p>
          ) : (
            alerts.map((alert) => (
              <article className="saved-address" key={alert.id}>
                <strong>{alert.title}</strong>
                <span>{alert.message}</span>
                <small>{formatDate(alert.created_at)}</small>
              </article>
            ))
          )}
        </section>
      )}

      <section className="customer-panel">
        <h2>
          {isRequest ? (
            <Heart size={20} />
          ) : (
            <MessageSquareText size={20} />
          )}
          {isRequest ? "Suggest a product" : "Customer feedback"}
        </h2>

        <p className="customer-muted">
          {isRequest
            ? "Tell us which grocery product you would like us to stock."
            : "Share feedback, rate your experience, or report a problem."}
        </p>

        {notice && <p className="customer-message success" role="status">{notice}</p>}
        {error && <p className="customer-message error" role="alert">{error}</p>}

        <form className="address-form" onSubmit={submit}>
          {!isRequest && (
            <label>
              Feedback type
              <select value={type} onChange={(e) => setType(e.target.value)}>
                <option value="GENERAL">General feedback</option>
                <option value="PRODUCT">Product</option>
                <option value="DELIVERY">Delivery</option>
                <option value="COMPLAINT">Problem / complaint</option>
              </select>
            </label>
          )}

          <label>
            {isRequest ? "Product name" : "Subject"}
            <input
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              minLength={3}
              maxLength={180}
              placeholder={isRequest ? "e.g. MTR dosa mix" : "Enter a subject"}
              required
            />
          </label>

          {!isRequest && (
            <label>
              Rating
              <select
                value={rating}
                onChange={(e) => setRating(e.target.value)}
              >
                <option value="5">5 - Excellent</option>
                <option value="4">4 - Good</option>
                <option value="3">3 - Okay</option>
                <option value="2">2 - Poor</option>
                <option value="1">1 - Very poor</option>
              </select>
            </label>
          )}

          <label>
            {isRequest ? "Product details" : "Details"}
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              minLength={5}
              maxLength={5000}
              rows={4}
              placeholder={
                isRequest
                  ? "Brand, package size, or other details"
                  : "Describe your experience"
              }
              required
            />
          </label>

          <button type="submit">
            <Send size={15} />
            {isRequest ? "Submit product request" : "Send feedback"}
          </button>
        </form>
      </section>

      <section className="customer-panel">
        <h3>{isRequest ? "Your product requests" : "Your feedback history"}</h3>

        {loading ? (
          <p className="customer-muted">Loading submissions...</p>
        ) : visibleItems.length === 0 ? (
          <p className="customer-muted">
            {isRequest
              ? "You have not requested any products yet."
              : "You have not submitted any feedback yet."}
          </p>
        ) : (
          visibleItems.map((item) => (
            <article className="saved-address" key={item.id}>
              <strong>{item.subject}</strong>
              <span>
                {item.feedback_type.replaceAll("_", " ")} · {item.status}
                {item.rating != null ? ` · ${item.rating}/5` : ""}
              </span>
              <span>{item.message}</span>
              {item.admin_response && (
                <span>Store reply: {item.admin_response}</span>
              )}
              <small>{formatDate(item.created_at)}</small>
            </article>
          ))
        )}
      </section>
    </div>
  );
}

// ADMIN: filter feedback and feature requests into separate sections.
export function AdminEngagement({
  token,
  mode = "feedback",
}: {
  token: string;
  mode?: EngagementMode;
}) {
  const [rows, setRows] = useState<Feedback[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const isRequest = mode === "requests";

  const load = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const response = await authFetch(
        `${API_URL}/engagement/admin/feedback`,
        token,
      );

      if (!response.ok) throw new Error(await errorText(response));

      setRows(await response.json());
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not load submissions.",
      );
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  async function save(row: Feedback) {
    setError("");

    try {
      const response = await authFetch(
        `${API_URL}/engagement/admin/feedback/${row.id}`,
        token,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            status: row.status,
            admin_response: row.admin_response || null,
          }),
        },
      );

      if (!response.ok) throw new Error(await errorText(response));

      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save changes.");
    }
  }

  const visibleRows = rows.filter((row) =>
    isRequest
      ? row.feedback_type === "FEATURE_REQUEST"
      : row.feedback_type !== "FEATURE_REQUEST",
  );

  return (
    <section className="admin-panel">
      <h2>
        <MessageSquareText size={20} />
        {isRequest ? "Product & feature requests" : "Customer feedback"}
      </h2>

      <p>
        {isRequest
          ? "Review product and feature requests submitted by customers."
          : "Review ratings, delivery feedback, product comments and complaints."}
      </p>

      {error && <p role="alert">{error}</p>}

      {loading ? (
        <p className="admin-muted">Loading submissions...</p>
      ) : visibleRows.length === 0 ? (
        <p className="admin-muted">
          No {isRequest ? "requests" : "feedback"} submitted yet.
        </p>
      ) : (
        <div className="admin-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Customer</th>
                <th>Type / rating</th>
                <th>Subject &amp; message</th>
                <th>Status</th>
                <th>Store reply</th>
                <th>Save</th>
              </tr>
            </thead>

            <tbody>
              {visibleRows.map((row) => (
                <tr key={row.id}>
                  <td>
                    {row.customer_name || "Customer"}
                    <small>{row.email}</small>
                  </td>

                  <td>
                    {row.feedback_type}
                    <small>
                      {row.rating != null ? `${row.rating}/5` : "No rating"}
                    </small>
                  </td>

                  <td>
                    <strong>{row.subject}</strong>
                    <small>{row.message}</small>
                  </td>

                  <td>
                    <select
                      aria-label={`Status for submission ${row.id}`}
                      value={row.status}
                      onChange={(e) =>
                        setRows((current) =>
                          current.map((item) =>
                            item.id === row.id
                              ? { ...item, status: e.target.value }
                              : item,
                          ),
                        )
                      }
                    >
                      {["NEW", "REVIEWING", "PLANNED", "RESOLVED", "CLOSED"].map(
                        (status) => (
                          <option key={status} value={status}>
                            {status}
                          </option>
                        ),
                      )}
                    </select>
                  </td>

                  <td>
                    <textarea
                      aria-label={`Reply for submission ${row.id}`}
                      rows={3}
                      value={row.admin_response || ""}
                      onChange={(e) =>
                        setRows((current) =>
                          current.map((item) =>
                            item.id === row.id
                              ? { ...item, admin_response: e.target.value }
                              : item,
                          ),
                        )
                      }
                    />
                  </td>

                  <td>
                    <button type="button" onClick={() => void save(row)}>
                      Save
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
