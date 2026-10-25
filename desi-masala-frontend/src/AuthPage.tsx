import { useEffect, useState, type FormEvent } from "react";
import { ArrowLeft, Eye, EyeOff, Leaf, LockKeyhole, Mail, Phone, UserRound } from "lucide-react";
import { loginCustomer, registerCustomer, verifyEmailCode, resendVerification, type AuthUser } from "./api";
import "./AuthPage.css";
import { lookupCity } from "./postcodeLookup";
import {useLanguage,languageOptions,type Language,} from "./LanguageContext";
type LanguageOption = {
  value: Language;
  label: string;
};

type AuthMode = "login" | "register";
interface AuthPageProps { onBack: () => void; onLogin: (user: AuthUser, token: string, expiresIn: number, rememberMe: boolean) => void }

export default function AuthPage({ onBack, onLogin }: AuthPageProps) {
  const [mode, setMode] = useState<AuthMode>("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [addressLine1, setAddressLine1] = useState("");
  const [postalCode, setPostalCode] = useState("");
  const [city, setCity] = useState("");
  const [country, setCountry] = useState("Germany");
  const { language, setLanguage } = useLanguage();
  const [marketingOptIn, setMarketingOptIn] = useState(true);
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [pendingVerificationEmail, setPendingVerificationEmail] = useState("");
  const [verificationCode, setVerificationCode] = useState("");

  useEffect(() => { let cancelled=false; const timer=window.setTimeout(async()=>{ if(postalCode.trim().length<3)return; const found=await lookupCity(postalCode,country); if(!cancelled&&found)setCity(found); },350); return ()=>{cancelled=true;window.clearTimeout(timer);}; },[postalCode,country]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setSuccess(""); setBusy(true);
    try {
      if (mode === "register") {
        const result = await registerCustomer({ name: name.trim(), email: email.trim(), phone: phone.trim(), date_of_birth: dateOfBirth, address_line1: addressLine1.trim(), postal_code: postalCode.trim(), city: city.trim(), country, marketing_opt_in: marketingOptIn, password });
        setPendingVerificationEmail(email.trim().toLowerCase());
        setSuccess(result.message);
      } else {
        const result = await loginCustomer({email: email.trim().toLowerCase(),password,account_type: "customer",remember_me: rememberMe,});
        onLogin(result.user,result.access_token,result.expires_in,rememberMe);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    } finally { setBusy(false); }
  }

  async function handleVerifyCode() {
    setBusy(true); setError(""); setSuccess("");
    try { const result = await verifyEmailCode(pendingVerificationEmail, verificationCode); setSuccess(result.message); setVerificationCode(""); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not verify the code."); }
    finally { setBusy(false); }
  }

  async function handleResendCode() {
    setBusy(true); setError(""); setSuccess("");
    try { const result = await resendVerification(pendingVerificationEmail || email.trim().toLowerCase()); setSuccess(result.message); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not resend the verification code."); }
    finally { setBusy(false); }
  }

  return (
    <main className="auth-page">
      <section className="auth-story">
        <button className="auth-back" onClick={onBack} type="button"><ArrowLeft size={17} /> Back to store</button>
        <div className="auth-story-inner">
          <div className="auth-logo"><span>🌿</span><div><strong>desi masala</strong><small>A TASTE OF HOME</small></div></div>
          <span className="auth-kicker"><Leaf size={15} /> YOUR INDIAN GROCERY STORE</span>
          <h1>A little taste of home, wherever life takes you.</h1>
          <p>Bring your favourite Indian pantry essentials to your table in Germany.</p>
          <div className="auth-food-art" aria-hidden="true"><span>🌶️</span><span>🍚</span><span>🫘</span><span>🌿</span><span>🍵</span></div>
          <div className="auth-trust"><LockKeyhole size={17} /><span>Your account details are protected. We never store your plain-text password.</span></div>
        </div>
      </section>
      <section className="auth-panel">
        <div className="auth-form-wrap"><label className="language-picker auth-language-picker"><span>Language</span><select value={language} onChange={e=>setLanguage(e.target.value as typeof language)}>{languageOptions.map((option: LanguageOption) => (<option key={option.value} value={option.value}>{option.label}</option>))}</select></label>
          <div className="auth-mobile-logo"><span>🌿</span><strong>desi masala</strong></div>
          <div className="auth-tabs" role="tablist" aria-label="Account options">
            <button type="button" role="tab" aria-selected={mode === "login"} className={mode === "login" ? "selected" : ""} onClick={() => { setMode("login"); setError(""); setSuccess(""); }}>Sign in</button>
            <button type="button" role="tab" aria-selected={mode === "register"} className={mode === "register" ? "selected" : ""} onClick={() => { setMode("register"); setError(""); setSuccess(""); }}>Create account</button>
          </div>
          <div className="auth-heading"><span>{mode === "login" ? "WELCOME BACK" : "JOIN OUR TABLE"}</span><h2>  {mode === "login"    ? "Good to see you again."    : "Make yourself at home."}</h2><p>  {mode === "login"    ? "Sign in to continue to your Desi Masala account."    : "Create an account for a more personal shopping experience."}</p></div>
          <form onSubmit={handleSubmit} className="auth-form">
            {mode === "register" && <label><span>Full name</span><div className="auth-input"><UserRound size={18}/><input autoComplete="name" value={name} onChange={e => setName(e.target.value)} placeholder="Your full name" required minLength={1} maxLength={100}/></div></label>}
            <label><span>Email address</span><div className="auth-input"><Mail size={18}/><input type="email" autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" required maxLength={254}/></div></label>
            {mode === "register" && <label><span>Phone number</span><div className="auth-input"><Phone size={18}/><input type="tel" autoComplete="tel" value={phone} onChange={e => setPhone(e.target.value)} placeholder="+49 123 456789" required minLength={5} maxLength={30}/></div></label>}
            {mode === "register" && <label><span>Date of birth (for birthday offers)</span><input type="date" value={dateOfBirth} max={new Date().toISOString().slice(0,10)} onChange={e=>setDateOfBirth(e.target.value)} required /></label>}
            {mode === "register" && <label><span>Delivery street address</span><input autoComplete="street-address" value={addressLine1} onChange={e=>setAddressLine1(e.target.value)} placeholder="Street and house number" required maxLength={200}/></label>}
            {mode === "register" && <label><span>Country</span><select value={country} onChange={e=>{setCountry(e.target.value);setCity("")}}><option>Germany</option><option>France</option><option>Spain</option><option>Poland</option><option>India</option><option>Netherlands</option><option>Belgium</option><option>Austria</option><option>Italy</option><option>Portugal</option></select></label>}
            {mode === "register" && <div className="auth-register-address-row"><label><span>Postcode / PIN code</span><input autoComplete="postal-code" value={postalCode} onChange={e=>setPostalCode(e.target.value)} required minLength={2} maxLength={20}/></label><label><span>City</span><input autoComplete="address-level2" value={city} onChange={e=>setCity(e.target.value)} required maxLength={100}/></label></div>}
            {mode === "register" && <label className="remember-me"><input type="checkbox" checked={marketingOptIn} onChange={e=>setMarketingOptIn(e.target.checked)}/><span>Email me new-stock alerts, special offers and birthday discounts (optional).</span></label>}
            <label><span>Password</span><div className="auth-input"><LockKeyhole size={18}/><input type={showPassword ? "text" : "password"} autoComplete={mode === "login" ? "current-password" : "new-password"} value={password} onChange={e => setPassword(e.target.value)} placeholder={mode === "login" ? "Enter your password" : "At least 8 characters"} required minLength={mode === "register" ? 8 : 1} maxLength={128}/><button type="button" className="password-toggle" onClick={() => setShowPassword(!showPassword)} aria-label={showPassword ? "Hide password" : "Show password"}>{showPassword ? <EyeOff size={17}/> : <Eye size={17}/>}</button></div>{mode === "register" && <small className="auth-help">Use at least 8 characters, including uppercase, lowercase, a number and a symbol.</small>}</label>
            {mode === "login" && <label className="remember-me"><input type="checkbox" checked={rememberMe} onChange={e => setRememberMe(e.target.checked)} /> <span>Keep me signed in on this device</span></label>}
            {error && <div className="auth-alert auth-error" role="alert">{error}</div>}
            {success && <div className="auth-alert auth-success" role="status">{success}</div>}
            <button className="auth-submit" type="submit" disabled={busy}>{busy ? "Please wait…" : mode === "login" ? "Sign in securely" : "Create my account"}</button>
          </form>
          {mode === "register" && pendingVerificationEmail && <section className="verify-code-panel"><h3>Verify your email</h3><p>Enter the six-digit code sent to <strong>{pendingVerificationEmail}</strong>. The code expires in 30 minutes.</p><label><span>Verification code</span><input inputMode="numeric" autoComplete="one-time-code" maxLength={6} pattern="[0-9]{6}" value={verificationCode} onChange={e=>setVerificationCode(e.target.value.replace(/\D/g, "").slice(0,6))} placeholder="123456"/></label><button type="button" className="auth-submit" disabled={busy || verificationCode.length!==6} onClick={()=>void handleVerifyCode()}>{busy?"Verifying…":"Verify email"}</button><button type="button" className="verify-resend" disabled={busy} onClick={()=>void handleResendCode()}>Resend verification code</button></section>}
          <p className="auth-switch">{mode === "login" ? "New to Desi Masala?" : "Already have an account?"} <button type="button" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); setSuccess(""); }}>{mode === "login" ? "Create an account" : "Sign in"}</button></p>
          <p className="auth-legal">By continuing, you agree to use Desi Masala responsibly. Email verification is required for new accounts.</p>
        </div>
      </section>
    </main>
  );
}
