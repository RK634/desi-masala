import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type Language = "en" | "de" | "fr" | "es" | "pl" | "hi";

const translations: Record<Exclude<Language, "en">, Record<string, string>> = {
  de: {
    "All Products":"Alle Produkte","Rice & Grains":"Reis & Getreide","Lentils & Beans":"Linsen & Bohnen","Spices":"Gewürze","Fresh Produce":"Frische Produkte","Pickles & Sauces":"Gurken & Saucen","Tea & Drinks":"Tee & Getränke","Other Groceries":"Weitere Lebensmittel",
    "Search rice, spices, lentils...":"Suche Reis, Gewürze, Linsen...","My Account":"Mein Konto","My account":"Mein Konto","Sign in":"Anmelden","Sign out":"Abmelden","Create account":"Konto erstellen","Cart":"Warenkorb","Shopping cart":"Warenkorb","Add":"Hinzufügen","Add to cart":"In den Warenkorb","Continue shopping":"Weiter einkaufen","Checkout":"Zur Kasse","Subtotal":"Zwischensumme","Total":"Gesamt","Discount":"Rabatt","Apply":"Anwenden","Promo code":"Aktionscode","Enter promo code":"Aktionscode eingeben","Delivery address":"Lieferadresse","Postcode":"Postleitzahl","City":"Stadt","Country":"Land","Language":"Sprache","Back to store":"Zurück zum Shop",
    "WELCOME BACK":"WILLKOMMEN ZURÜCK","Good to see you again.":"Schön, dass du wieder da bist.","Sign in to continue to your Desi Masala account.":"Melde dich an, um dein Desi-Masala-Konto zu öffnen.","JOIN OUR TABLE":"WILLKOMMEN AM TISCH","Make yourself at home.":"Fühl dich wie zu Hause.","Create an account for a more personal shopping experience.":"Erstelle ein Konto für ein persönlicheres Einkaufserlebnis.",
    "YOUR INDIAN GROCERY STORE":"DEIN INDISCHER LEBENSMITTELSHOP","A little taste of home, wherever life takes you.":"Ein Stück Heimat, wohin das Leben dich auch führt.","Bring your favourite Indian pantry essentials to your table in Germany.":"Entdecke deine indischen Vorratslieblinge für deinen Tisch in Deutschland.","Your account details are protected. We never store your plain-text password.":"Deine Kontodaten sind geschützt. Wir speichern niemals Passwörter im Klartext.",
    "Loading products...":"Produkte werden geladen...","No products found":"Keine Produkte gefunden","Available":"Verfügbar","In stock":"Auf Lager","Out of stock":"Nicht auf Lager","Place order":"Bestellung aufgeben","Order history":"Bestellverlauf","Orders & Tracking":"Bestellungen & Sendungsverfolgung","My Profile":"Mein Profil","Addresses":"Adressen","Payment Information":"Zahlungsinformationen","Notifications":"Benachrichtigungen","Feedback & Support":"Feedback & Support","Product Requests":"Produktwünsche","Customer support":"Kundensupport","Refresh":"Aktualisieren","Subject":"Betreff","Category":"Kategorie","Your message":"Deine Nachricht","Create support ticket":"Supportanfrage erstellen","Reply":"Antworten","Send":"Senden","Loading...":"Wird geladen...","Save":"Speichern","Cancel":"Abbrechen","Delete":"Löschen","Edit":"Bearbeiten","Search":"Suchen","Dashboard":"Dashboard","Inventory":"Lagerbestand","Products":"Produkte","Orders":"Bestellungen","Low stock":"Niedriger Lagerbestand","Add product":"Produkt hinzufügen","Notification":"Benachrichtigungen","Customer support queue":"Kundensupport-Warteschlange","Delivery exceptions":"Lieferprobleme"
  },
  fr: {
    "All Products":"Tous les produits","Rice & Grains":"Riz et céréales","Lentils & Beans":"Lentilles et haricots","Spices":"Épices","Fresh Produce":"Produits frais","Pickles & Sauces":"Pickles et sauces","Tea & Drinks":"Thés et boissons","Other Groceries":"Autres produits alimentaires",
    "Search rice, spices, lentils...":"Rechercher riz, épices, lentilles...","My Account":"Mon compte","My account":"Mon compte","Sign in":"Se connecter","Sign out":"Se déconnecter","Create account":"Créer un compte","Cart":"Panier","Shopping cart":"Panier","Add":"Ajouter","Add to cart":"Ajouter au panier","Continue shopping":"Continuer les achats","Checkout":"Paiement","Subtotal":"Sous-total","Total":"Total","Discount":"Remise","Apply":"Appliquer","Promo code":"Code promo","Enter promo code":"Saisir le code promo","Delivery address":"Adresse de livraison","Postcode":"Code postal","City":"Ville","Country":"Pays","Language":"Langue","Back to store":"Retour à la boutique",
    "WELCOME BACK":"BON RETOUR","Good to see you again.":"Ravi de vous revoir.","Sign in to continue to your Desi Masala account.":"Connectez-vous à votre compte Desi Masala.","JOIN OUR TABLE":"REJOIGNEZ-NOUS","Make yourself at home.":"Faites comme chez vous.","Create an account for a more personal shopping experience.":"Créez un compte pour une expérience d’achat personnalisée.",
    "YOUR INDIAN GROCERY STORE":"VOTRE ÉPICERIE INDIENNE","A little taste of home, wherever life takes you.":"Un goût de chez vous, où que la vie vous mène.","Bring your favourite Indian pantry essentials to your table in Germany.":"Retrouvez vos essentiels indiens préférés sur votre table en Allemagne.","Your account details are protected. We never store your plain-text password.":"Vos données sont protégées. Nous ne stockons jamais votre mot de passe en clair.",
    "Loading products...":"Chargement des produits...","No products found":"Aucun produit trouvé","Available":"Disponible","In stock":"En stock","Out of stock":"Épuisé","Place order":"Commander","Order history":"Historique des commandes","Orders & Tracking":"Commandes et suivi","My Profile":"Mon profil","Addresses":"Adresses","Payment Information":"Informations de paiement","Notifications":"Notifications","Feedback & Support":"Commentaires et assistance","Product Requests":"Demandes de produits","Customer support":"Service client","Refresh":"Actualiser","Subject":"Objet","Category":"Catégorie","Your message":"Votre message","Create support ticket":"Créer une demande d’assistance","Reply":"Répondre","Send":"Envoyer","Loading...":"Chargement...","Save":"Enregistrer","Cancel":"Annuler","Delete":"Supprimer","Edit":"Modifier","Search":"Rechercher","Dashboard":"Tableau de bord","Inventory":"Stock","Products":"Produits","Orders":"Commandes","Low stock":"Stock faible","Add product":"Ajouter un produit","Customer support queue":"File du service client","Delivery exceptions":"Incidents de livraison"
  },
  es: {
    "All Products":"Todos los productos","Rice & Grains":"Arroz y cereales","Lentils & Beans":"Lentejas y legumbres","Spices":"Especias","Fresh Produce":"Productos frescos","Pickles & Sauces":"Encurtidos y salsas","Tea & Drinks":"Té y bebidas","Other Groceries":"Otros alimentos",
    "Search rice, spices, lentils...":"Buscar arroz, especias, lentejas...","My Account":"Mi cuenta","My account":"Mi cuenta","Sign in":"Iniciar sesión","Sign out":"Cerrar sesión","Create account":"Crear cuenta","Cart":"Carrito","Shopping cart":"Carrito","Add":"Añadir","Add to cart":"Añadir al carrito","Continue shopping":"Seguir comprando","Checkout":"Finalizar compra","Subtotal":"Subtotal","Total":"Total","Discount":"Descuento","Apply":"Aplicar","Promo code":"Código promocional","Enter promo code":"Introducir código","Delivery address":"Dirección de entrega","Postcode":"Código postal","City":"Ciudad","Country":"País","Language":"Idioma","Back to store":"Volver a la tienda",
    "WELCOME BACK":"TE DAMOS LA BIENVENIDA","Good to see you again.":"Qué bueno verte de nuevo.","Sign in to continue to your Desi Masala account.":"Inicia sesión en tu cuenta de Desi Masala.","JOIN OUR TABLE":"ÚNETE A NOSOTROS","Make yourself at home.":"Siéntete como en casa.","Create an account for a more personal shopping experience.":"Crea una cuenta para una experiencia más personal.",
    "YOUR INDIAN GROCERY STORE":"TU TIENDA DE COMESTIBLES INDIOS","A little taste of home, wherever life takes you.":"Un pedacito de hogar, dondequiera que vayas.","Bring your favourite Indian pantry essentials to your table in Germany.":"Lleva tus productos indios favoritos a tu mesa en Alemania.","Your account details are protected. We never store your plain-text password.":"Tus datos están protegidos. Nunca guardamos tu contraseña en texto plano.",
    "Loading products...":"Cargando productos...","No products found":"No se encontraron productos","Available":"Disponible","In stock":"En stock","Out of stock":"Agotado","Place order":"Realizar pedido","Order history":"Historial de pedidos","Orders & Tracking":"Pedidos y seguimiento","My Profile":"Mi perfil","Addresses":"Direcciones","Payment Information":"Información de pago","Notifications":"Notificaciones","Feedback & Support":"Comentarios y soporte","Product Requests":"Solicitudes de productos","Customer support":"Atención al cliente","Refresh":"Actualizar","Subject":"Asunto","Category":"Categoría","Your message":"Tu mensaje","Create support ticket":"Crear solicitud de soporte","Reply":"Responder","Send":"Enviar","Loading...":"Cargando...","Save":"Guardar","Cancel":"Cancelar","Delete":"Eliminar","Edit":"Editar","Search":"Buscar","Dashboard":"Panel","Inventory":"Inventario","Products":"Productos","Orders":"Pedidos","Low stock":"Pocas existencias","Add product":"Añadir producto","Customer support queue":"Cola de atención al cliente","Delivery exceptions":"Incidencias de entrega"
  },
  pl: {
    "All Products":"Wszystkie produkty","Rice & Grains":"Ryż i zboża","Lentils & Beans":"Soczewica i fasola","Spices":"Przyprawy","Fresh Produce":"Świeże produkty","Pickles & Sauces":"Pikle i sosy","Tea & Drinks":"Herbata i napoje","Other Groceries":"Pozostałe artykuły spożywcze",
    "Search rice, spices, lentils...":"Szukaj ryżu, przypraw, soczewicy...","My Account":"Moje konto","My account":"Moje konto","Sign in":"Zaloguj się","Sign out":"Wyloguj się","Create account":"Utwórz konto","Cart":"Koszyk","Shopping cart":"Koszyk","Add":"Dodaj","Add to cart":"Dodaj do koszyka","Continue shopping":"Kontynuuj zakupy","Checkout":"Do kasy","Subtotal":"Suma częściowa","Total":"Razem","Discount":"Rabat","Apply":"Zastosuj","Promo code":"Kod promocyjny","Enter promo code":"Wpisz kod promocyjny","Delivery address":"Adres dostawy","Postcode":"Kod pocztowy","City":"Miasto","Country":"Kraj","Language":"Język","Back to store":"Wróć do sklepu",
    "WELCOME BACK":"WITAMY PONOWNIE","Good to see you again.":"Miło znów Cię widzieć.","Sign in to continue to your Desi Masala account.":"Zaloguj się do konta Desi Masala.","JOIN OUR TABLE":"DOŁĄCZ DO NAS","Make yourself at home.":"Poczuj się jak w domu.","Create an account for a more personal shopping experience.":"Utwórz konto, aby korzystać z bardziej spersonalizowanych zakupów.",
    "YOUR INDIAN GROCERY STORE":"TWÓJ INDYJSKI SKLEP SPOŻYWCZY","A little taste of home, wherever life takes you.":"Smak domu, gdziekolwiek jesteś.","Bring your favourite Indian pantry essentials to your table in Germany.":"Poznaj ulubione indyjskie produkty spożywcze w Niemczech.","Your account details are protected. We never store your plain-text password.":"Twoje dane są chronione. Nigdy nie przechowujemy hasła w postaci jawnej.",
    "Loading products...":"Ładowanie produktów...","No products found":"Nie znaleziono produktów","Available":"Dostępne","In stock":"W magazynie","Out of stock":"Brak w magazynie","Place order":"Złóż zamówienie","Order history":"Historia zamówień","Orders & Tracking":"Zamówienia i śledzenie","My Profile":"Mój profil","Addresses":"Adresy","Payment Information":"Informacje o płatności","Notifications":"Powiadomienia","Feedback & Support":"Opinie i pomoc","Product Requests":"Prośby o produkty","Customer support":"Obsługa klienta","Refresh":"Odśwież","Subject":"Temat","Category":"Kategoria","Your message":"Twoja wiadomość","Create support ticket":"Utwórz zgłoszenie","Reply":"Odpowiedz","Send":"Wyślij","Loading...":"Ładowanie...","Save":"Zapisz","Cancel":"Anuluj","Delete":"Usuń","Edit":"Edytuj","Search":"Szukaj","Dashboard":"Panel","Inventory":"Magazyn","Products":"Produkty","Orders":"Zamówienia","Low stock":"Niski stan","Add product":"Dodaj produkt","Customer support queue":"Kolejka obsługi klienta","Delivery exceptions":"Problemy z dostawą"
  },
  hi: {
    "All Products":"सभी उत्पाद","Rice & Grains":"चावल और अनाज","Lentils & Beans":"दालें और फलियाँ","Spices":"मसाले","Fresh Produce":"ताज़ी उपज","Pickles & Sauces":"अचार और सॉस","Tea & Drinks":"चाय और पेय","Other Groceries":"अन्य किराना",
    "Search rice, spices, lentils...":"चावल, मसाले, दाल खोजें...","My Account":"मेरा खाता","My account":"मेरा खाता","Sign in":"साइन इन","Sign out":"साइन आउट","Create account":"खाता बनाएँ","Cart":"कार्ट","Shopping cart":"शॉपिंग कार्ट","Add":"जोड़ें","Add to cart":"कार्ट में जोड़ें","Continue shopping":"खरीदारी जारी रखें","Checkout":"चेकआउट","Subtotal":"उप-योग","Total":"कुल","Discount":"छूट","Apply":"लागू करें","Promo code":"प्रोमो कोड","Enter promo code":"प्रोमो कोड दर्ज करें","Delivery address":"डिलीवरी पता","Postcode":"पिन कोड","City":"शहर","Country":"देश","Language":"भाषा","Back to store":"स्टोर पर वापस जाएँ",
    "WELCOME BACK":"वापसी पर स्वागत है","Good to see you again.":"आपको फिर देखकर अच्छा लगा।","Sign in to continue to your Desi Masala account.":"अपने देसी मसाला खाते में जाने के लिए साइन इन करें।","JOIN OUR TABLE":"हमसे जुड़ें","Make yourself at home.":"अपने घर जैसा महसूस करें।","Create an account for a more personal shopping experience.":"बेहतर खरीदारी अनुभव के लिए खाता बनाएँ।",
    "YOUR INDIAN GROCERY STORE":"आपकी भारतीय किराना दुकान","A little taste of home, wherever life takes you.":"जहाँ भी रहें, घर का स्वाद पाएँ।","Bring your favourite Indian pantry essentials to your table in Germany.":"जर्मनी में अपने पसंदीदा भारतीय किराना उत्पाद घर लाएँ।","Your account details are protected. We never store your plain-text password.":"आपके खाते की जानकारी सुरक्षित है। हम पासवर्ड को सादे टेक्स्ट में नहीं रखते।",
    "Loading products...":"उत्पाद लोड हो रहे हैं...","No products found":"कोई उत्पाद नहीं मिला","Available":"उपलब्ध","In stock":"स्टॉक में","Out of stock":"स्टॉक खत्म","Place order":"ऑर्डर दें","Order history":"ऑर्डर इतिहास","Orders & Tracking":"ऑर्डर और ट्रैकिंग","My Profile":"मेरी प्रोफ़ाइल","Addresses":"पते","Payment Information":"भुगतान जानकारी","Notifications":"सूचनाएँ","Feedback & Support":"प्रतिक्रिया और सहायता","Product Requests":"उत्पाद अनुरोध","Customer support":"ग्राहक सहायता","Refresh":"रिफ्रेश करें","Subject":"विषय","Category":"श्रेणी","Your message":"आपका संदेश","Create support ticket":"सहायता टिकट बनाएँ","Reply":"जवाब दें","Send":"भेजें","Loading...":"लोड हो रहा है...","Save":"सहेजें","Cancel":"रद्द करें","Delete":"हटाएँ","Edit":"बदलें","Search":"खोजें","Dashboard":"डैशबोर्ड","Inventory":"इन्वेंटरी","Products":"उत्पाद","Orders":"ऑर्डर","Low stock":"कम स्टॉक","Add product":"उत्पाद जोड़ें","Customer support queue":"ग्राहक सहायता कतार","Delivery exceptions":"डिलीवरी समस्याएँ"
  }
};

const baseLabels: Record<string,string> = {
  language:"Language",cart:"Cart",signIn:"Sign in",signOut:"Sign out",myAccount:"My account",adminDashboard:"Admin dashboard",
  search:"Search rice, spices, lentils...",shoppingCart:"Shopping cart",deliveryOrder:"Delivery and order",deliveryAddress:"Delivery address",
  chooseAddress:"Choose an address",warehouse:"Fulfilment warehouse",chooseWarehouse:"Choose warehouse",continueCheckout:"Continue to checkout",
  continueShopping:"Continue shopping",placeOrder:"Place order · manual payment",placingOrder:"Placing order…",apply:"Apply",promoCode:"Promo code",
  promoPlaceholder:"Enter promo code",discount:"Discount",subtotal:"Subtotal",total:"Total",discountApplied:"Discount applied",
  invalidPromo:"Could not apply this promo code.",postcode:"Postcode",city:"City",country:"Country",firstOrder:"First order discount",loyaltyDiscount:"Loyalty discount",
  addToCart:"Add to cart",loading:"Loading...",save:"Save",cancel:"Cancel"
};

const LanguageContext = createContext<{language:Language;setLanguage:(l:Language)=>void;t:(key:string)=>string}>({
  language:"en",setLanguage:()=>{},t:(key)=>baseLabels[key] ?? key
});

function translateText(value: string, language: Language): string {
  if (language === "en") return value;
  const dictionary = translations[language];
  const trimmed = value.trim();
  const translated = dictionary[trimmed];
  if (!translated) return value;
  return value.replace(trimmed, translated);
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(() => {
    try {
      const saved = localStorage.getItem("desi-masala-language");
      return saved && ["en","de","fr","es","pl","hi"].includes(saved) ? saved as Language : "en";
    } catch { return "en"; }
  });

  const setLanguage = (next: Language) => {
    try { localStorage.setItem("desi-masala-language", next); } catch {}
    setLanguageState(next);
  };

  useEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.setAttribute("data-language", language);
    const originalText = new WeakMap<Text, string>();
    const originalAttrs = new WeakMap<Element, Map<string,string>>();
    let scheduled = false;

    const translateElement = (root: Node) => {
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      let node: Node | null;
      while ((node = walker.nextNode())) {
        const textNode = node as Text;
        if (!textNode.parentElement || ["SCRIPT","STYLE","NOSCRIPT","TEXTAREA"].includes(textNode.parentElement.tagName)) continue;
        if (!originalText.has(textNode)) originalText.set(textNode, textNode.nodeValue ?? "");
        const original = originalText.get(textNode) ?? "";
        const translated = translateText(original, language);
        if (textNode.nodeValue !== translated) textNode.nodeValue = translated;
      }

      const elements = root instanceof Element ? [root, ...Array.from(root.querySelectorAll("*"))] : root instanceof Document ? [root.documentElement, ...Array.from(root.querySelectorAll("*"))] : [];
      for (const el of elements) {
        for (const attr of ["placeholder","title","aria-label","alt"]) {
          if (!el.hasAttribute(attr)) continue;
          let attrs = originalAttrs.get(el);
          if (!attrs) { attrs = new Map(); originalAttrs.set(el, attrs); }
          if (!attrs.has(attr)) attrs.set(attr, el.getAttribute(attr) ?? "");
          const original = attrs.get(attr) ?? "";
          const translated = translateText(original, language);
          if (el.getAttribute(attr) !== translated) el.setAttribute(attr, translated);
        }
      }
    };

    translateElement(document.body);
    const observer = new MutationObserver((records) => {
      if (scheduled) return;
      scheduled = true;
      queueMicrotask(() => {
        scheduled = false;
        for (const record of records) {
          if (record.type === "characterData" && record.target instanceof Text) {
            const textNode = record.target;
            const original = originalText.get(textNode) ?? textNode.nodeValue ?? "";
            originalText.set(textNode, original);
            const translated = translateText(original, language);
            if (textNode.nodeValue !== translated) textNode.nodeValue = translated;
          }
          for (const added of Array.from(record.addedNodes)) {
            if (added.nodeType === Node.ELEMENT_NODE || added.nodeType === Node.TEXT_NODE) translateElement(added);
          }
          if (record.type === "attributes" && record.target instanceof Element) translateElement(record.target);
        }
      });
    });
    observer.observe(document.body, {subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:["placeholder","title","aria-label","alt"]});
    return () => observer.disconnect();
  }, [language]);

  const value = useMemo(() => ({
    language,
    setLanguage,
    t: (key: string) => language === "en" ? (baseLabels[key] ?? key) : (translations[language][baseLabels[key] ?? key] ?? baseLabels[key] ?? key)
  }), [language]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() { return useContext(LanguageContext); }

export const languageOptions: Array<{value:Language;label:string}> = [
  {value:"en",label:"English"},{value:"de",label:"Deutsch"},{value:"fr",label:"Français"},
  {value:"es",label:"Español"},{value:"pl",label:"Polski"},{value:"hi",label:"हिन्दी"}
];
