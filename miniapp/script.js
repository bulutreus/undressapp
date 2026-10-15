const SUPPORTED_LANGS = ["en", "tr", "ar"];
const DEFAULT_LANG = "en";
const LANG_STORAGE_KEY = "hottok_lang";

const I18N = {
  en: {
    "lang.label": "EN",
    "store.title": "Store",
    "store.sub": "Purchase diamonds with Telegram Stars.",
    "store.featureTitle": "Unlimited Energy",
    "store.featureText": "Remove the barriers. Gain endless energy!",
    "store.featureCta": "🚀 Let's go",
    "store.bestOffer": "Best Offer",
    "store.note": "When you tap a pack, bot chat opens and payment continues with Telegram Stars.",
    "tabs.undress": "Undress",
    "tabs.sex": "Sex",
    "tabs.videoPresets": "Presets",
    "tabs.videoCustom": "Custom Prompt",
    "gallery.title": "Your Gallery",
    "gallery.empty": "No generated images yet.",
    "loading.title": "Creating…",
    "loading.sub": "Your image is being generated. Please wait.",
    "upload.styleTitle": "Style",
    "upload.yourPhoto": "Your photo",
    "upload.dropText": "Tap to select a photo",
    "upload.dropHint": "Clear, front-facing photos work best",
    "upload.before": "Before",
    "upload.after": "After",
    "upload.compareHint": "Drag the slider to compare",
    "upload.resultTitle": "Result",
    "upload.resultEmpty": "Your result will appear here after generation",
    "upload.download": "Download",
    "upload.generateAgain": "Generate again",
    "upload.generate": "Generate",
    "nav.video": "Video",
    "nav.image": "Image",
    "nav.gallery": "Gallery",
    "status.insufficientDiamonds": "Insufficient diamonds. Please buy more in the store.",
    "status.noPhoto": "Please select a photo first.",
    "status.generationStarted": "Generation started… please wait.",
    "status.generationFailed": "Generation failed. Please try again.",
    "status.savedToGallery": "Saved to your gallery.",
    "status.customPromptPlaceholder": "Describe the video scene you want…",
    "status.videoCustomCost": "Cost per custom video: 💎 20",
    "status.runCustomVideo": "Generate Custom Video",
    "errors.network": "Network error. Please check your connection.",
    "errors.telegramInit": "Could not verify Telegram user.",
  },
  tr: {
    "lang.label": "TR",
    "store.title": "Mağaza",
    "store.sub": "Telegram Stars ile elmas satın alın.",
    "store.featureTitle": "Sınırsız Enerji",
    "store.featureText": "Engelleri kaldırın. Sonsuz enerji kazanın!",
    "store.featureCta": "🚀 Hadi başlayalım",
    "store.bestOffer": "En İyi Teklif",
    "store.note": "Bir pakete dokunduğunuzda bot sohbeti açılır ve ödeme Telegram Stars ile devam eder.",
    "tabs.undress": "Çıplaklaştır",
    "tabs.sex": "Seks",
    "tabs.videoPresets": "Hazır Şablonlar",
    "tabs.videoCustom": "Özel Prompt",
    "gallery.title": "Galeriniz",
    "gallery.empty": "Henüz oluşturulmuş görsel yok.",
    "loading.title": "Oluşturuluyor…",
    "loading.sub": "Görseliniz oluşturuluyor. Lütfen bekleyin.",
    "upload.styleTitle": "Stil",
    "upload.yourPhoto": "Fotoğrafın",
    "upload.dropText": "Fotoğraf seçmek için dokun",
    "upload.dropHint": "Net, önden çekilmiş fotoğraflar en iyi sonucu verir",
    "upload.before": "Önce",
    "upload.after": "Sonra",
    "upload.compareHint": "Karşılaştırmak için kaydırıcıyı sürükleyin",
    "upload.resultTitle": "Sonuç",
    "upload.resultEmpty": "Sonuç oluşturulduktan sonra burada görünecek",
    "upload.download": "İndir",
    "upload.generateAgain": "Tekrar oluştur",
    "upload.generate": "Oluştur",
    "nav.video": "Video",
    "nav.image": "Görsel",
    "nav.gallery": "Galeri",
    "status.insufficientDiamonds": "Yetersiz elmas. Lütfen mağazadan daha fazla satın alın.",
    "status.noPhoto": "Lütfen önce bir fotoğraf seçin.",
    "status.generationStarted": "Oluşturma başladı… lütfen bekleyin.",
    "status.generationFailed": "Oluşturma başarısız. Lütfen tekrar deneyin.",
    "status.savedToGallery": "Galerinize kaydedildi.",
    "status.customPromptPlaceholder": "İstediğiniz video sahnesini açıklayın…",
    "status.videoCustomCost": "Özel video başına maliyet: 💎 20",
    "status.runCustomVideo": "Özel Video Oluştur",
    "errors.network": "Ağ hatası. Lütfen bağlantınızı kontrol edin.",
    "errors.telegramInit": "Telegram kullanıcısı doğrulanamadı.",
  },
  ar: {
    "lang.label": "AR",
    "store.title": "المتجر",
    "store.sub": "شراء الماس عبر نجوم تيليجرام.",
    "store.featureTitle": "طاقة غير محدودة",
    "store.featureText": "أزل الحواجز. احصل على طاقة لا تنتهي!",
    "store.featureCta": "🚀 هيا بنا",
    "store.bestOffer": "أفضل عرض",
    "store.note": "عند النقر على حزمة، يفتح دردشة البوت ويتم الدفع بنجوم تيليجرام.",
    "tabs.undress": "تخلع الملابس",
    "tabs.sex": "جنس",
    "tabs.videoPresets": "قوالب جاهزة",
    "tabs.videoCustom": "وصف مخصص",
    "gallery.title": "معرضك",
    "gallery.empty": "لا توجد صور مُنشأة بعد.",
    "loading.title": "جارٍ الإنشاء…",
    "loading.sub": "يتم إنشاء صورتك. يرجى الانتظار.",
    "upload.styleTitle": "النمط",
    "upload.yourPhoto": "صورتك",
    "upload.dropText": "اضغط لاختيار صورة",
    "upload.dropHint": "الصور الواضحة الأمامية تعطي أفضل نتيجة",
    "upload.before": "قبل",
    "upload.after": "بعد",
    "upload.compareHint": "اسحب المؤشر للمقارنة",
    "upload.resultTitle": "النتيجة",
    "upload.resultEmpty": "ستظهر النتيجة هنا بعد الإنشاء",
    "upload.download": "تحميل",
    "upload.generateAgain": "إنشاء مرة أخرى",
    "upload.generate": "إنشاء",
    "nav.video": "فيديو",
    "nav.image": "صورة",
    "nav.gallery": "المعرض",
    "status.insufficientDiamonds": "الماس غير كافٍ. يرجى شراء المزيد من المتجر.",
    "status.noPhoto": "يرجى اختيار صورة أولاً.",
    "status.generationStarted": "بدء الإنشاء… يرجى الانتظار.",
    "status.generationFailed": "فشل الإنشاء. يرجى المحاولة مرة أخرى.",
    "status.savedToGallery": "تم الحفظ في معرضك.",
    "status.customPromptPlaceholder": "صف مشهد الفيديو الذي تريده…",
    "status.videoCustomCost": "التكلفة لكل فيديو مخصص: 💎 20",
    "status.runCustomVideo": "إنشاء فيديو مخصص",
    "errors.network": "خطأ في الشبكة. يرجى التحقق من الاتصال.",
    "errors.telegramInit": "تعذر التحقق من مستخدم تيليجرام.",
  },
};

function t(key, lang) {
  const l = lang || currentLang || DEFAULT_LANG;
  const bundle = I18N[l] || I18N[DEFAULT_LANG];
  return bundle[key] || (I18N[DEFAULT_LANG][key] ?? key);
}

let currentLang = DEFAULT_LANG;

function resolveInitialLanguage() {
  try {
    const stored = localStorage.getItem(LANG_STORAGE_KEY);
    if (stored && SUPPORTED_LANGS.includes(stored)) return stored;
  } catch (_) {}
  try {
    const tg = window.Telegram?.WebApp;
    const tgLang = tg?.initDataUnsafe?.user?.language_code;
    if (tgLang) {
      const short = String(tgLang).slice(0, 2).toLowerCase();
      if (SUPPORTED_LANGS.includes(short)) return short;
    }
  } catch (_) {}
  const nav = (navigator?.language || "").slice(0, 2).toLowerCase();
  if (SUPPORTED_LANGS.includes(nav)) return nav;
  return DEFAULT_LANG;
}

function applyTranslations(lang) {
  currentLang = lang;
  const isRtl = lang === "ar";
  document.documentElement.setAttribute("lang", lang);
  document.documentElement.setAttribute("dir", isRtl ? "rtl" : "ltr");
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (key) el.textContent = t(key, lang);
  });
  const label = document.getElementById("langCurrentLabel");
  if (label) label.textContent = t("lang.label", lang);
  const placeholderElements = [
    { id: "customPromptInput", key: "status.customPromptPlaceholder" },
  ];
  placeholderElements.forEach(({ id, key }) => {
    const el = document.getElementById(id);
    if (el) el.setAttribute("placeholder", t(key, lang));
  });
}

function setLanguage(lang, opts) {
  const safe = SUPPORTED_LANGS.includes(lang) ? lang : DEFAULT_LANG;
  try {
    localStorage.setItem(LANG_STORAGE_KEY, safe);
  } catch (_) {}
  applyTranslations(safe);
  if (opts && typeof opts.onChange === "function") opts.onChange(safe);
}

function cycleLanguage() {
  const idx = SUPPORTED_LANGS.indexOf(currentLang);
  const next = SUPPORTED_LANGS[(idx + 1) % SUPPORTED_LANGS.length];
  setLanguage(next);
}

function initLanguageSystem() {
  const initial = resolveInitialLanguage();
  currentLang = initial;
  applyTranslations(initial);
  const btn = document.getElementById("langToggleBtn");
  if (btn) {
    btn.addEventListener("click", cycleLanguage);
  }
}

const undressFiles = ["undress.avif", "bikini.avif", "shibari.avif", "lingerie.avif", "bdsm.avif", "xray.avif"];

const sexFiles = [
  "ass.avif",
  "bath.webp",
  "bbc.avif",
  "blowjob.avif",
  "cowgirl.avif",
  "cumshot.avif",
  "dancing.avif",
  "doggy.avif",
  "feet.avif",
  "fingering.avif",
  "flashing.avif",
  "hand-bra.webp",
  "handjob.avif",
  "kneeling.avif",
  "leaked.avif",
  "missionary.avif",
  "pussy.avif",
  "removing-panties.avif",
  "selfie.avif",
  "showering.avif",
  "side.avif",
  "spread-ass.avif",
  "spread-legs.avif",
  "standing.avif",
  "titsjob.avif",
  "upskirt.avif",
];

const videoPresetFiles = [
  "undress.mp4",
  "riding.mp4",
  "blowjob.mp4",
  "handjob.mp4",
  "double-penetration.mp4",
  "spit-roast.mp4",
  "ahegao.mp4",
  "anal.mp4",
  "bare-feet.mp4",
  "bouncy-tits.mp4",
  "breast-insertion.mp4",
  "bukkake.mp4",
  "cumshot.mp4",
  "deepthroat.mp4",
  "dick-kiss.mp4",
  "dildo.mp4",
  "doggy.mp4",
  "drill.mp4",
  "fingering.mp4",
  "french-kiss.mp4",
  "heleed-feet.mp4",
  "huge-cum.mp4",
  "missionary.mp4",
  "mouth-cum.mp4",
  "pregnant.mp4",
  "pussy-licking.mp4",
  "sex-spoon.mp4",
  "show-pussy.mp4",
  "squirt.mp4",
  "stocking-feet.mp4",
  "twerk.mp4",
  "xl-breast.mp4",
];

const customPromptVideoFile = "custom-prompt-orange-scene.mp4";
const VIDEO_PREVIEW_BASE = "/undress/video";
const VIDEO_PREVIEW_ANIM_BASE = "/undress/video/previews";

const diamondBadgeIcon = '<span class="card-badge__diamond" aria-hidden="true">💎</span>';
const DEFAULT_CARD_PRICES = Object.freeze({
  undress: 1,
  sex: 2,
  video: 20,
});
let cardPrices = { ...DEFAULT_CARD_PRICES };
let currentDiamondBalance = null;
let miniappConfig = null;

function formatDiamondBalance(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  return n.toFixed(1);
}

function applyDiamondBalance(value) {
  const el = document.getElementById("diamondBalance");
  if (value == null) {
    currentDiamondBalance = null;
    if (el) el.textContent = "💎 --";
    updateCardLocks();
    return;
  }
  const formatted = formatDiamondBalance(value);
  if (formatted !== null) {
    currentDiamondBalance = Number(formatted);
    if (el) el.textContent = `💎 ${formatted}`;
  } else {
    currentDiamondBalance = null;
    if (el) el.textContent = "💎 --";
  }
  updateCardLocks();
}
const galleryState = {
  files: [],
  rendered: 0,
  batchSize: 4,
};
let imageGridsRendered = false;
const gifPreviewState = {
  idlePrefetchStarted: false,
};
const videoPreviewState = {
  observer: null,
  playing: new Set(),
  maxConcurrent: 5,
};

function cardBadge(price) {
  return `${diamondBadgeIcon}<span class="card-badge__price">${price}</span>`;
}

function resolveCardPrice(category) {
  const safeCategory = category || "undress";
  if (safeCategory === "video") return cardPrices.video;
  if (safeCategory === "sex") return cardPrices.sex;
  return cardPrices.undress;
}

function applyCardPricesFromConfig(prices) {
  if (!prices || typeof prices !== "object") return;
  const next = { ...cardPrices };
  if (Number.isFinite(Number(prices.undress))) next.undress = Number(prices.undress);
  if (Number.isFinite(Number(prices.sex))) next.sex = Number(prices.sex);
  if (Number.isFinite(Number(prices.video))) next.video = Number(prices.video);
  cardPrices = next;
  document.querySelectorAll(".media-card--action[data-media-category]").forEach((card) => {
    const category = card.dataset.mediaCategory || "undress";
    const type = card.dataset.mediaType || "image";
    const price = type === "video" ? cardPrices.video : resolveCardPrice(category);
    card.dataset.price = String(price);
    const badge = card.querySelector(".card-badge__price");
    if (badge) badge.textContent = String(price);
  });
  updateCardLocks();
}

/** Kart gorsel yolundan dosya adi (bikini.avif) — sunucu data/card_prompts.txt ile eslestirir. */
function cardKeyFromSrc(src) {
  if (!src) return "";
  const part = String(src).split("/").pop() || "";
  return (part.split("?")[0] || "").trim();
}

function getTelegramInitData() {
  return (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) || "";
}

function applyTelegramUi() {
  /* Telegram WebApp — no extra UI toggles */
}

function telegramClientUser() {
  const tg = window.Telegram && window.Telegram.WebApp;
  return (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) || null;
}

function userDisplayName(user) {
  if (!user) return "Profile";
  const first = (user.first_name || "").trim();
  const last = (user.last_name || "").trim();
  const username = (user.username || "").trim();
  if (first || last) return [first, last].filter(Boolean).join(" ");
  if (username) return `@${username}`;
  return "Profile";
}

function userInitials(user) {
  if (!user) return "?";
  const first = (user.first_name || "").trim();
  const last = (user.last_name || "").trim();
  const username = (user.username || "").trim();
  if (first && last) return (first[0] + last[0]).toUpperCase();
  if (first) return first.slice(0, 2).toUpperCase();
  if (username) return username.slice(0, 2).toUpperCase();
  return "?";
}

function setAvatarInitials(avatarEl, user, displayName) {
  if (!avatarEl || !user) return;
  const initials = userInitials(user);
  const canvas = document.createElement("canvas");
  canvas.width = 128;
  canvas.height = 128;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const hue = Math.abs(Number(user.id) || 0) % 360;
  ctx.fillStyle = `hsl(${hue}, 52%, 40%)`;
  ctx.fillRect(0, 0, 128, 128);
  ctx.fillStyle = "#fff";
  ctx.font = "bold 46px Inter, Segoe UI, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(initials, 64, 66);
  avatarEl.src = canvas.toDataURL("image/png");
  avatarEl.alt = displayName || userDisplayName(user);
}

function applyAvatarPhoto(avatarEl, photoUrl, fallbackUser, displayName) {
  if (!avatarEl || !photoUrl) {
    if (fallbackUser) setAvatarInitials(avatarEl, fallbackUser, displayName);
    return;
  }
  avatarEl.alt = displayName || userDisplayName(fallbackUser);
  avatarEl.src = photoUrl;
  avatarEl.onerror = () => {
    avatarEl.onerror = null;
    if (fallbackUser) setAvatarInitials(avatarEl, fallbackUser, displayName);
  };
}

async function applyTelegramUserProfile() {
  const avatar = document.getElementById("profileAvatar");
  if (!avatar) return;

  const clientUser = telegramClientUser();
  if (clientUser) {
    avatar.alt = userDisplayName(clientUser);
    if (clientUser.photo_url) {
      applyAvatarPhoto(avatar, clientUser.photo_url, clientUser);
    }
  }

  const initData = getTelegramInitData();
  if (!initData) {
    if (clientUser && !clientUser.photo_url) setAvatarInitials(avatar, clientUser);
    return;
  }

  try {
    const r = await fetch("/api/miniapp/profile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ init_data: initData }),
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok || !j.ok) {
      if (clientUser && !clientUser.photo_url) setAvatarInitials(avatar, clientUser);
      return;
    }
    if (typeof j.diamonds !== "undefined") {
      applyDiamondBalance(j.diamonds);
    }
    const displayName = j.display_name || userDisplayName(clientUser);
    avatar.alt = displayName;
    if (j.photo_url) {
      applyAvatarPhoto(avatar, j.photo_url, clientUser, displayName);
    } else if (clientUser) {
      setAvatarInitials(avatar, clientUser, displayName);
    }
  } catch {
    if (clientUser && !clientUser.photo_url) setAvatarInitials(avatar, clientUser);
  }
}

async function syncDiamondBalance() {
  const initData = getTelegramInitData();
  if (!initData) {
    applyDiamondBalance(null);
    return;
  }
  try {
    const r = await fetch("/api/miniapp/balance", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ init_data: initData }),
    });
    const j = await r.json().catch(() => ({}));
    if (r.ok && j.ok && typeof j.diamonds !== "undefined") {
      applyDiamondBalance(j.diamonds);
      return;
    }
    const el = document.getElementById("diamondBalance");
    if (el && el.textContent === "💎 --") {
      el.textContent = "💎 ?";
    }
  } catch {
    const el = document.getElementById("diamondBalance");
    if (el) el.textContent = "💎 ?";
    currentDiamondBalance = null;
    updateCardLocks();
  }
}

function escapeHtml(text) {
  const d = document.createElement("div");
  d.textContent = text == null ? "" : String(text);
  return d.innerHTML;
}

function fileStem(fileName) {
  return String(fileName || "")
    .replace(/\.[^.]+$/, "")
    .toLowerCase();
}

function videoPreviewUrl(fileName, basePath) {
  return `${basePath}/${String(fileName || "").replace(/^\/+/, "")}`;
}

function videoAnimCandidates(fileName) {
  const stem = fileStem(fileName);
  return [
    `${VIDEO_PREVIEW_ANIM_BASE}/${stem}.webp`,
    `${VIDEO_PREVIEW_ANIM_BASE}/${stem}.gif`,
    `${VIDEO_PREVIEW_BASE}/${stem}.webp`,
    `${VIDEO_PREVIEW_BASE}/${stem}.gif`,
  ];
}

function initVideoCardPreview(card, fileName) {
  if (!card || !fileName || card.dataset.previewInit === "1") return;
  card.dataset.previewInit = "1";

  const posterImg = card.querySelector(".preview-video-poster");
  const animImg = card.querySelector(".preview-gif");

  if (posterImg) {
    initVideoPosterImg(posterImg, fileName);
  }

  if (animImg) {
    loadVideoCardGif(card, animImg, fileName);
  }

  observeVideoPreviews(card);
}

function loadVideoCardGif(card, animImg, fileName) {
  const posterCandidates = videoPosterCandidates(fileName);
  const animCandidates = videoAnimCandidates(fileName);
  const candidates = [...posterCandidates, ...animCandidates];
  let idx = 0;

  const tryNext = () => {
    if (idx >= candidates.length) return;
    const url = candidates[idx];
    idx += 1;
    animImg.onload = () => {
      if (animImg.naturalWidth < 8) {
        tryNext();
        return;
      }
      card.dataset.previewMode = "gif";
      animImg.classList.add("is-loaded");
      const poster = card.querySelector(".preview-video-poster");
      if (poster) poster.classList.add("is-hidden");
    };
    animImg.onerror = tryNext;
    animImg.src = url;
  };

  tryNext();
}

function primeVisibleMp4InCard(card) {
  if (!card || card.dataset.previewMode === "gif") return;
  const video = card.querySelector(".preview-video");
  if (!video) return;
  const rect = card.getBoundingClientRect();
  if (rect.bottom < -120 || rect.top > window.innerHeight + 120) return;
  card.classList.add("preview-mode-mp4");
  ensureVideoSource(video, false);
  queueVideoPlay(video);
}

function refreshVideoTabPreviews() {
  const panel = document.querySelector('[data-panel="video"]');
  if (!panel || !panel.classList.contains("is-active")) return;
  panel.querySelectorAll(".media-card--video[data-video-file], .custom-video-hero[data-video-file]").forEach((card) => {
    if (card.dataset.previewMode !== "gif") {
      primeVisibleMp4InCard(card);
    }
  });
}

function setupVideoScrollRefresh() {
  let timer = 0;
  window.addEventListener(
    "scroll",
    () => {
      if (appState.lastView !== "video") return;
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        timer = 0;
        refreshVideoTabPreviews();
      }, 100);
    },
    { passive: true }
  );
}

function prefetchGifPreviews() {
  if (gifPreviewState.idlePrefetchStarted) return;
  gifPreviewState.idlePrefetchStarted = true;
  const prefetchTargets = [];
  videoPresetFiles.slice(0, 8).forEach((file) => {
    const cands = videoPosterCandidates(file).slice(0, 2);
    prefetchTargets.push(...cands);
  });
  prefetchTargets.filter(Boolean).slice(0, 12).forEach((url, index) => {
    setTimeout(() => {
      const link = document.createElement("link");
      link.rel = "prefetch";
      link.as = "image";
      link.href = url;
      document.head.appendChild(link);
    }, index * 150);
  });
}

/** Video adiyla ayni klasorde poster (webp/jpg) — yoksa videodan kare yakalanir. */
function videoPosterCandidates(fileName) {
  const stem = fileStem(fileName);
  const candidates = [
    `${VIDEO_PREVIEW_BASE}/${stem}.webp`,
    `${VIDEO_PREVIEW_BASE}/${stem}.jpg`,
    `${VIDEO_PREVIEW_BASE}/${stem}.jpeg`,
    `${VIDEO_PREVIEW_BASE}/${stem}.avif`,
    `${VIDEO_PREVIEW_BASE}/posters/${stem}.webp`,
    `${VIDEO_PREVIEW_BASE}/posters/${stem}.jpg`,
  ];

  const undressMatch = undressFiles.find((f) => fileStem(f) === stem);
  if (undressMatch) candidates.push(`./undress/photo/${undressMatch}`);

  const sexMatch = sexFiles.find((f) => fileStem(f) === stem);
  if (sexMatch) candidates.push(`./sex/${sexMatch}`);

  return [...new Set(candidates)];
}

function videoPosterUrl(fileName) {
  return videoPosterCandidates(fileName)[0];
}

function initVideoPosterImg(img, fileName) {
  if (!img || !fileName) return;
  const candidates = videoPosterCandidates(fileName);
  img.dataset.posterTry = "0";
  img.removeAttribute("src");

  const tryNext = () => {
    const idx = Number(img.dataset.posterTry || 0);
    if (idx >= candidates.length) {
      img.classList.add("is-poster-missing");
      return;
    }
    img.dataset.posterTry = String(idx + 1);
    img.src = candidates[idx];
  };

  img.onload = () => {
    if (img.naturalWidth > 8) {
      img.dataset.posterOk = "1";
      img.classList.remove("is-poster-missing");
      const card = img.closest(".media-card--video, .custom-video-hero");
      if (card && card.dataset.previewMode !== "gif") {
        card.dataset.previewMode = "poster";
      }
    } else {
      tryNext();
    }
  };
  img.onerror = tryNext;
  tryNext();
}

/** Telegram WebView <a download> often fails; try Bot API downloadFile, else blob. */
async function downloadGalleryImage(url, filename) {
  const u = String(url || "").trim();
  if (!u) return;
  const name = String(filename || "image.png").replace(/[/\\?*:|"<>]/g, "_") || "image.png";
  const tg = window.Telegram && window.Telegram.WebApp;
  if (tg && typeof tg.downloadFile === "function") {
    try {
      tg.downloadFile({ url: u, file_name: name });
      return;
    } catch (err) {
      // fall through: blob
    }
  }
  try {
    const r = await fetch(u, { mode: "cors", credentials: "same-origin" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    const blob = await r.blob();
    const obj = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = obj;
    a.download = name;
    a.style.display = "none";
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () {
      try {
        URL.revokeObjectURL(obj);
      } catch (e) {
        /* ignore */
      }
    }, 2500);
  } catch (err) {
    const msg = err && err.message ? err.message : "Download failed.";
    if (window.alert) window.alert(msg);
  }
}

function renderGalleryItem(f) {
  const u = f.url || "";
  const src = u.startsWith("http") ? u : `${location.origin}${u}`;
  const name = f.name || "output";
  const rel = f.rel != null && String(f.rel).trim() !== "" ? String(f.rel) : u.replace(/^\/outputs\//, "");
  const relEnc = encodeURIComponent(rel);
  return `<article class="media-card gallery-item" data-gallery-rel="${relEnc}">
  <img src=${JSON.stringify(src)} alt=${JSON.stringify(String(name))} loading="lazy" decoding="async" class="gallery-item__img" />
  <div class="gallery-item__actions" role="group" aria-label="Gallery">
    <button type="button" class="gallery-item__btn gallery-item__btn--download" data-gallery-download="1" data-dl-href=${JSON.stringify(src)} data-dl-name=${JSON.stringify(String(name))}>Download</button>
    <button type="button" class="gallery-item__btn gallery-item__btn--delete" data-gallery-delete="1" data-relpath="${relEnc}">Delete</button>
  </div>
</article>`;
}

function renderNextGalleryBatch() {
  const grid = document.getElementById("galleryGrid");
  const empty = document.getElementById("galleryEmptyText");
  if (!grid || !empty) return;
  if (!galleryState.files.length) {
    empty.textContent = "No generated images yet.";
    return;
  }
  const start = galleryState.rendered;
  if (start >= galleryState.files.length) return;
  const end = Math.min(start + galleryState.batchSize, galleryState.files.length);
  const html = galleryState.files.slice(start, end).map(renderGalleryItem).join("");
  grid.insertAdjacentHTML("beforeend", html);
  galleryState.rendered = end;
  empty.textContent = "";
}

function maybeRenderMoreGalleryOnScroll() {
  if (appState.lastView !== "gallery") return;
  if (galleryState.rendered >= galleryState.files.length) return;
  const bottom = window.scrollY + window.innerHeight;
  const threshold = document.documentElement.scrollHeight - 180;
  if (bottom >= threshold) {
    renderNextGalleryBatch();
  }
}

async function loadGallery() {
  const grid = document.getElementById("galleryGrid");
  const empty = document.getElementById("galleryEmptyText");
  if (!grid || !empty) return;
  const initData = getTelegramInitData();
  if (!initData) {
    empty.textContent = "Open from Telegram to view your gallery.";
    grid.innerHTML = "";
    galleryState.files = [];
    galleryState.rendered = 0;
    return;
  }
  try {
    const r = await fetch("/api/miniapp/gallery", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ init_data: initData }),
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) {
      const d = j.detail;
      const msg = typeof d === "string" ? d : (Array.isArray(d) && d[0] && d[0].msg) || "Could not load gallery.";
      empty.textContent = String(msg);
      grid.innerHTML = "";
      galleryState.files = [];
      galleryState.rendered = 0;
      return;
    }
    const files = Array.isArray(j.files) ? j.files : [];
    galleryState.files = files;
    galleryState.rendered = 0;
    grid.innerHTML = "";
    renderNextGalleryBatch();
  } catch {
    empty.textContent = "Gallery could not be loaded.";
    grid.innerHTML = "";
    galleryState.files = [];
    galleryState.rendered = 0;
  }
}

function setupGalleryActions() {
  const grid = document.getElementById("galleryGrid");
  if (!grid || grid._galleryDeleteBound) return;
  grid._galleryDeleteBound = true;
  grid.addEventListener("click", async (e) => {
    const downloadBtn = e.target && e.target.closest("button[data-gallery-download]");
    if (downloadBtn) {
      e.preventDefault();
      e.stopPropagation();
      const href = downloadBtn.getAttribute("data-dl-href");
      const fname = downloadBtn.getAttribute("data-dl-name");
      if (href) {
        await downloadGalleryImage(href, fname);
      }
      return;
    }
    const btn = e.target && e.target.closest("button[data-gallery-delete]");
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();
    const relEnc = btn.getAttribute("data-relpath");
    if (!relEnc) return;
    const rel = decodeURIComponent(relEnc);
    if (!confirm("Delete this file?")) return;
    const initData = getTelegramInitData();
    if (!initData) {
      return;
    }
    const card = btn.closest(".gallery-item");
    const empty = document.getElementById("galleryEmptyText");
    const parent = card && card.parentNode;
    const nextSibling = card && card.nextSibling;
    if (card && parent) {
      parent.removeChild(card);
      if (empty && !grid.querySelector(".gallery-item")) {
        empty.textContent = "No generated images yet.";
      }
    }
    try {
      let res = await fetch("/api/miniapp/gallery/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ init_data: initData, rel }),
      });
      if (res.status === 405) {
        res = await fetch("/api/miniapp/gallery/delete", {
          method: "DELETE",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ init_data: initData, rel }),
        });
      }
      const j = await res.json().catch(() => ({}));
      if (!res.ok) {
        const d = j.detail;
        const msg = typeof d === "string" ? d : (Array.isArray(d) && d[0] && d[0].msg) || `HTTP ${res.status}`;
        if (card && parent) {
          if (nextSibling) parent.insertBefore(card, nextSibling);
          else parent.appendChild(card);
        }
        if (empty && grid.querySelector(".gallery-item")) {
          empty.textContent = "";
        }
        alert(msg);
        return;
      }
      galleryState.files = galleryState.files.filter((item) => {
        const raw = item && item.rel != null ? String(item.rel) : "";
        return raw !== rel;
      });
      galleryState.rendered = grid.querySelectorAll(".gallery-item").length;
      if (!grid.querySelector(".gallery-item") && galleryState.files.length > 0) {
        renderNextGalleryBatch();
      }
    } catch (err) {
      if (card && parent) {
        if (nextSibling) parent.insertBefore(card, nextSibling);
        else parent.appendChild(card);
      }
      if (empty && grid.querySelector(".gallery-item")) {
        empty.textContent = "";
      }
      alert(err && err.message ? err.message : "Could not delete.");
    }
  });
  if (!grid._galleryScrollBound) {
    grid._galleryScrollBound = true;
    window.addEventListener("scroll", maybeRenderMoreGalleryOnScroll, { passive: true });
  }
}

function initTelegramWebApp() {
  const tg = window.Telegram && window.Telegram.WebApp;
  if (!tg) return;
  try {
    tg.ready();
  } catch {
    // ignore
  }
  try {
    tg.expand();
  } catch {
    // ignore
  }
  try {
    if (typeof tg.setBackgroundColor === "function") tg.setBackgroundColor("#000000");
    if (typeof tg.setHeaderColor === "function") tg.setHeaderColor("#000000");
  } catch {
    // ignore
  }
  if (getTelegramInitData()) {
    applyTelegramUserProfile();
    syncDiamondBalance();
  }
  if (!document._diamondVisibilityBound) {
    document._diamondVisibilityBound = true;
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible" && getTelegramInitData()) {
        syncDiamondBalance();
      }
    });
  }
}

const appState = {
  selectedCard: null,
  lastView: "image",
  lastImageTab: "undress",
  lastVideoTab: "presets",
  fromVideoCustomPrompt: false,
  lastResultUrl: "",
  lastResultName: "",
  beforePhotoUrl: "",
  comparePosition: 50,
};

function updateCardLocks() {
  const cards = document.querySelectorAll(".media-card--action");
  cards.forEach((card) => {
    const price = Number(card.dataset.price || 0);
    const locked = Number.isFinite(currentDiamondBalance) && currentDiamondBalance < price;
    card.classList.toggle("is-locked", locked);
    card.setAttribute("aria-disabled", locked ? "true" : "false");
  });
}

async function getMiniappConfig() {
  if (miniappConfig) return miniappConfig;
  try {
    const r = await fetch("/api/miniapp/config");
    const j = await r.json();
    miniappConfig = j && j.ok ? j : { ok: false, buy_url: "" };
    if (miniappConfig.prices) applyCardPricesFromConfig(miniappConfig.prices);
  } catch {
    miniappConfig = { ok: false, buy_url: "" };
  }
  return miniappConfig;
}

function setupStoreModal() {
  const openBtn = document.getElementById("openStoreBtn");
  const modal = document.getElementById("storeModal");
  const closeBtn = document.getElementById("closeStoreBtn");
  if (!openBtn || !modal || !closeBtn) return;

  const openStore = () => {
    syncDiamondBalance();
    modal.classList.remove("is-hidden");
    modal.setAttribute("aria-hidden", "false");
  };

  const closeStore = () => {
    modal.classList.add("is-hidden");
    modal.setAttribute("aria-hidden", "true");
  };

  openBtn.addEventListener("click", openStore);
  closeBtn.addEventListener("click", closeStore);
  modal.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    if (target.closest("[data-store-close]")) {
      closeStore();
      return;
    }
    const buyBtn = target.closest("[data-store-buy]");
    if (!buyBtn) return;
    closeStore();
    redirectToBuy(0);
  });
}

async function redirectToBuy(_requiredPrice) {
  const cfg = await getMiniappConfig();
  const buyUrl = (cfg && cfg.buy_url) || "";
  if (buyUrl) {
    const tg = window.Telegram && window.Telegram.WebApp;
    if (tg && typeof tg.openTelegramLink === "function") {
      tg.openTelegramLink(buyUrl);
    } else {
      window.open(buyUrl, "_blank", "noopener,noreferrer");
    }
    if (tg && typeof tg.close === "function") {
      setTimeout(() => {
        try {
          tg.close();
        } catch {
          // ignore
        }
      }, 100);
    }
    return;
  }
  if (window.Telegram?.WebApp?.showAlert) {
    window.Telegram.WebApp.showAlert("Set BOT_USERNAME in .env to enable the buy link.");
  } else {
    alert("Use /buy in the bot.");
  }
}

function prettifyLabel(name, index) {
  const raw = name.replace(/\.[^.]+$/, "");
  const parts = raw.split("-");
  const safe = parts.every((part) => part.length <= 2) ? `Item ${index + 1}` : raw;
  return safe.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function renderImageCards({ targetId, files, basePath, labelMap, category }) {
  const grid = document.getElementById(targetId);
  if (!grid) return;
  grid.innerHTML = files
    .map((file, index) => {
      const label = (labelMap && labelMap[file]) || prettifyLabel(file, index);
      const src = `${basePath}/${file}`;
      const safeCategory = category || "undress";
      const price = resolveCardPrice(safeCategory);
      return `
      <article class="media-card media-card--action" data-media-type="image" data-media-category="${safeCategory}" data-media-src="${src}" data-media-label="${label}" data-price="${price}">
        <span class="card-badge" aria-hidden="true">${cardBadge(price)}</span>
        <img src="${src}" alt="${label}" loading="lazy" decoding="async" fetchpriority="low" />
        <p class="card-label">${label}</p>
      </article>`;
    })
    .join("");
}

function ensureImageGridsRendered() {
  if (imageGridsRendered) return;
  imageGridsRendered = true;
  renderImageCards({
    targetId: "undressGrid",
    files: undressFiles,
    basePath: "./undress/photo",
    category: "undress",
    labelMap: {
      "undress.avif": "UNDRESS",
      "bikini.avif": "BIKINI",
      "shibari.avif": "SHIBARI",
      "lingerie.avif": "LINGERIE",
      "bdsm.avif": "BDSM",
      "xray.avif": "X RAY",
    },
  });
  renderImageCards({
    targetId: "sexGrid",
    files: sexFiles,
    basePath: "./sex",
    category: "sex",
  });
  updateCardLocks();
}

function renderVideoCards(targetId, files) {
  const videoGrid = document.getElementById(targetId);
  videoGrid.innerHTML = files
    .map((file, index) => {
      const label = prettifyLabel(file, index);
      const src = videoPreviewUrl(file, VIDEO_PREVIEW_BASE);
      const price = resolveCardPrice("video");
      const eager = index < 6 ? "eager" : "lazy";
      const priority = index < 4 ? "high" : "low";
      return `
      <article class="media-card media-card--action media-card--video" data-media-type="video" data-media-category="video" data-media-src="${src}" data-media-label="${label}" data-price="${price}" data-video-file="${file}">
        <span class="card-badge" aria-hidden="true">${cardBadge(price)}</span>
        <img class="preview-video-poster is-poster-missing" data-video-file="${file}" alt="" loading="${eager}" decoding="async" fetchpriority="${priority}" aria-hidden="true" />
        <img class="preview-gif" alt="${label}" loading="${eager}" decoding="async" fetchpriority="${priority}" />
        <video class="preview-video" data-src="${src}" data-video-file="${file}" muted playsinline loop preload="none" aria-label="${label}"></video>
        <p class="card-label">${label}</p>
      </article>`;
    })
    .join("");
  videoGrid.querySelectorAll(".media-card--video[data-video-file]").forEach((card) => {
    initVideoCardPreview(card, card.dataset.videoFile);
  });
}

function renderCustomPromptPanel() {
  const panel = document.getElementById("videoCustomPanel");
  panel.innerHTML = `
    <article class="custom-video-hero" data-video-file="${customPromptVideoFile}">
      <img class="preview-video-poster custom-hero-poster is-poster-missing" data-video-file="${customPromptVideoFile}" alt="" loading="eager" decoding="async" aria-hidden="true" />
      <img class="preview-gif custom-hero-gif" alt="Custom prompt" loading="eager" decoding="async" />
      <video class="preview-video custom-hero-video" data-src="${videoPreviewUrl(customPromptVideoFile, VIDEO_PREVIEW_BASE)}" data-video-file="${customPromptVideoFile}" muted playsinline loop preload="none" aria-label="Custom prompt"></video>
    </article>

    <div class="custom-prompt-block">
      <label class="custom-prompt-label" for="customVideoPromptInput" data-i18n="tabs.videoCustom">Custom Prompt</label>
      <div class="custom-prompt-input-wrap">
        <textarea
          id="customVideoPromptInput"
          class="custom-prompt-textarea"
          maxlength="300"
          rows="5"
          placeholder="Unleash your wildest fantasy..."
          spellcheck="false"
          autocomplete="off"
        ></textarea>
        <span class="custom-prompt-count" id="customVideoPromptCount" aria-live="polite">0/300</span>
      </div>
      <button type="button" class="custom-prompt-continue" id="customPromptContinueBtn" data-i18n="status.runCustomVideo">Generate Custom Video</button>
    </div>
  `;
  const ta = panel.querySelector("#customVideoPromptInput");
  if (ta) ta.setAttribute("placeholder", t("status.customPromptPlaceholder"));
  const btn = panel.querySelector("#customPromptContinueBtn");
  if (btn) btn.textContent = t("status.runCustomVideo");
  const lab = panel.querySelector(".custom-prompt-label");
  if (lab) lab.textContent = t("tabs.videoCustom");
  setupCustomPromptPanel();
  const hero = panel.querySelector(".custom-video-hero[data-video-file]");
  if (hero) initVideoCardPreview(hero, customPromptVideoFile);
}

function setupCustomPromptPanel() {
  const ta = document.getElementById("customVideoPromptInput");
  const cnt = document.getElementById("customVideoPromptCount");
  const btn = document.getElementById("customPromptContinueBtn");
  if (ta && cnt) {
    const update = () => {
      cnt.textContent = `${ta.value.length}/300`;
    };
    ta.addEventListener("input", update);
    update();
  }
  if (btn) {
    btn.addEventListener("click", () => {
      const src = videoPreviewUrl(customPromptVideoFile, VIDEO_PREVIEW_BASE);
      openUploadScreen({
        label: "Custom prompt",
        src,
        type: "video",
        category: "video",
        price: resolveCardPrice("video"),
        fromCustom: true,
      });
    });
  }
}

function setupTabs() {
  const topTabNav = document.querySelector(".tab-nav:not(.video-tab-nav)");
  const tabButtons = topTabNav.querySelectorAll(".tab-btn");
  const bottomItems = document.querySelectorAll(".bottom-item[data-view]");
  const panels = document.querySelectorAll(".panel");

  function activateImageTab(tabName) {
    appState.lastImageTab = tabName;
    tabButtons.forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.tab === tabName);
    });

    panels.forEach((panel) => {
      panel.classList.toggle("is-active", panel.dataset.panel === tabName);
    });
  }

  function activateBottomView(viewName) {
    appState.lastView = viewName;
    bottomItems.forEach((item) => {
      item.classList.toggle("is-active", item.dataset.view === viewName);
    });

    if (viewName === "video") {
      topTabNav.classList.add("is-hidden");
      panels.forEach((panel) => {
        panel.classList.toggle("is-active", panel.dataset.panel === "video");
      });
      if (typeof window.activateVideoTab === "function") {
        window.activateVideoTab(appState.lastVideoTab || "presets");
      } else {
        refreshVideoTabPreviews();
      }
      return;
    }
    pauseAllVideoPreviews();
    if (viewName === "gallery") {
      topTabNav.classList.add("is-hidden");
      panels.forEach((panel) => {
        panel.classList.toggle("is-active", panel.dataset.panel === "gallery");
      });
      loadGallery();
      return;
    }

    topTabNav.classList.remove("is-hidden");
    ensureImageGridsRendered();
    activateImageTab(appState.lastImageTab || "undress");
  }

  tabButtons.forEach((button) => {
    button.addEventListener("click", () => {
      activateImageTab(button.dataset.tab);
    });
  });

  bottomItems.forEach((button) => {
    button.addEventListener("click", () => {
      activateBottomView(button.dataset.view);
    });
  });

  window.activateBottomView = activateBottomView;
  window.activateImageTab = activateImageTab;
  activateBottomView("image");
}

function setupVideoTabs() {
  const videoTabButtons = document.querySelectorAll(".video-tab-btn");
  const videoGrids = document.querySelectorAll(".video-grid");

  function activateVideoTab(tabName) {
    appState.lastVideoTab = tabName;
    videoTabButtons.forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.videoTab === tabName);
    });

    videoGrids.forEach((grid) => {
      const isPresetGrid = grid.id === "videoPresetsGrid";
      grid.classList.toggle(
        "is-active",
        (tabName === "presets" && isPresetGrid) || (tabName === "custom" && !isPresetGrid)
      );
    });
    refreshVideoTabPreviews();
  }

  videoTabButtons.forEach((button) => {
    button.addEventListener("click", () => {
      activateVideoTab(button.dataset.videoTab);
    });
  });

  window.activateVideoTab = activateVideoTab;
  activateVideoTab("presets");
}

function setupCardActions() {
  document.addEventListener("click", (event) => {
    const card = event.target.closest(".media-card--action");
    if (!card) return;
    if (card.classList.contains("is-locked")) {
      const price = Number(card.dataset.price || 0);
      const balanceText = Number.isFinite(currentDiamondBalance) ? Number(currentDiamondBalance).toFixed(1) : "--";
      const message = `Not enough diamonds. Required: 💎 ${price} | Balance: 💎 ${balanceText}`;
      if (window.Telegram?.WebApp?.showAlert) {
        window.Telegram.WebApp.showAlert(message);
      } else {
        alert(message);
      }
      return;
    }

    openUploadScreen({
      label: card.dataset.mediaLabel,
      src: card.dataset.mediaSrc,
      type: card.dataset.mediaType,
      category: card.dataset.mediaCategory || "undress",
      price: Number(card.dataset.price || cardPrices.undress),
      fromCustom: false,
    });
  });
}

function openUploadScreen(selectedCard) {
  appState.selectedCard = selectedCard;
  appState.fromVideoCustomPrompt = Boolean(selectedCard && selectedCard.fromCustom);
  const uploadPanel = document.querySelector('[data-panel="upload"]');
  const allPanels = document.querySelectorAll(".panel");
  const topTabNav = document.querySelector(".tab-nav:not(.video-tab-nav)");
  const bottomNav = document.querySelector(".bottom-nav");
  const selectedPreview = document.getElementById("selectedCardPreview");
  const titleEl = document.getElementById("uploadStyleTitle");
  const costEl = document.getElementById("uploadStyleCost");
  const price = selectedCard.price || cardPrices.undress;

  allPanels.forEach((panel) => panel.classList.remove("is-active"));
  uploadPanel.classList.add("is-active");
  topTabNav.classList.add("is-hidden");
  bottomNav.classList.add("is-hidden");
  pauseAllVideoPreviews();

  if (selectedCard.type === "video") {
    selectedPreview.innerHTML = `<video src="${selectedCard.src}" autoplay muted loop playsinline></video>`;
  } else {
    selectedPreview.innerHTML = `<img src="${selectedCard.src}" alt="${selectedCard.label}" />`;
  }

  if (titleEl) titleEl.textContent = selectedCard.label || "Style";
  if (costEl) costEl.textContent = `💎 ${price}`;
  resetUploadResult();
  hideGenLoading();
  updateComfyStatus("");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function resetUploadResult() {
  appState.lastResultUrl = "";
  appState.lastResultName = "";
  hidePhotoCompare();
  const resultCard = document.getElementById("resultCard");
  const empty = document.getElementById("resultEmptyState");
  const wrap = document.getElementById("resultMediaWrap");
  const img = document.getElementById("comfyResultImage");
  const video = document.getElementById("comfyResultVideo");
  const videoWrap = document.getElementById("resultVideoWrap");
  if (resultCard) resultCard.classList.remove("is-visible");
  if (empty) empty.style.display = "";
  if (wrap) wrap.classList.add("is-hidden");
  if (videoWrap) videoWrap.classList.add("is-hidden");
  if (img) {
    img.src = "";
    img.classList.add("is-hidden");
  }
  if (video) {
    video.pause();
    video.removeAttribute("src");
    video.load();
  }
}

function getCompareFrame() {
  return document.getElementById("photoCompareFrame");
}

function syncCompareFrameWidth() {
  const frame = getCompareFrame();
  const beforeImg = document.getElementById("photoCompareBefore");
  if (!frame || !beforeImg) return;
  const w = frame.clientWidth;
  if (w > 0) beforeImg.style.width = `${w}px`;
}

function setComparePosition(pct) {
  const pos = Math.max(0, Math.min(100, Number(pct) || 0));
  appState.comparePosition = pos;
  const frame = getCompareFrame();
  const handle = document.getElementById("photoCompareHandle");
  if (frame) frame.style.setProperty("--compare-pct", String(pos));
  if (handle) handle.setAttribute("aria-valuenow", String(Math.round(pos)));
}

function showPhotoCompare(beforeSrc, afterSrc) {
  const wrap = document.getElementById("photoCompareWrap");
  const dropzone = document.getElementById("photoDropzone");
  const title = document.getElementById("yourPhotoTitle");
  const beforeImg = document.getElementById("photoCompareBefore");
  const afterImg = document.getElementById("photoCompareAfter");
  if (!wrap || !beforeImg || !afterImg || !beforeSrc || !afterSrc) return;

  beforeImg.src = beforeSrc;
  afterImg.src = afterSrc;
  if (dropzone) dropzone.classList.add("is-hidden");
  wrap.classList.remove("is-hidden");
  wrap.setAttribute("aria-hidden", "false");
  if (title) title.textContent = "Before & After";

  const onReady = () => {
    syncCompareFrameWidth();
    setComparePosition(appState.comparePosition || 50);
  };
  if (beforeImg.complete && afterImg.complete) onReady();
  else {
    beforeImg.onload = onReady;
    afterImg.onload = onReady;
  }
}

function hidePhotoCompare() {
  const wrap = document.getElementById("photoCompareWrap");
  const dropzone = document.getElementById("photoDropzone");
  const title = document.getElementById("yourPhotoTitle");
  const beforeImg = document.getElementById("photoCompareBefore");
  const afterImg = document.getElementById("photoCompareAfter");
  if (wrap) {
    wrap.classList.add("is-hidden");
    wrap.setAttribute("aria-hidden", "true");
  }
  if (dropzone) dropzone.classList.remove("is-hidden");
  if (title) title.textContent = "Your photo";
  if (beforeImg) beforeImg.removeAttribute("src");
  if (afterImg) afterImg.removeAttribute("src");
  setComparePosition(50);
}

function setupPhotoCompare() {
  const frame = getCompareFrame();
  const handle = document.getElementById("photoCompareHandle");
  if (!frame || !handle) return;

  let dragging = false;
  let frameRect = null;
  let rafId = 0;
  let pendingPct = null;

  const applyPosition = (pct) => {
    setComparePosition(pct);
  };

  const flushPosition = () => {
    rafId = 0;
    if (pendingPct == null) return;
    applyPosition(pendingPct);
    pendingPct = null;
  };

  const queuePosition = (pct) => {
    pendingPct = pct;
    if (!rafId) rafId = requestAnimationFrame(flushPosition);
  };

  const pctFromClientX = (clientX) => {
    if (!frameRect || !frameRect.width) return appState.comparePosition;
    return ((clientX - frameRect.left) / frameRect.width) * 100;
  };

  const onPointerMove = (event) => {
    if (!dragging) return;
    event.preventDefault();
    queuePosition(pctFromClientX(event.clientX));
  };

  const endDrag = () => {
    if (!dragging) return;
    dragging = false;
    frame.classList.remove("is-dragging");
    frameRect = null;
    if (rafId) {
      cancelAnimationFrame(rafId);
      rafId = 0;
      flushPosition();
    }
    window.removeEventListener("pointermove", onPointerMove);
    window.removeEventListener("pointerup", endDrag);
    window.removeEventListener("pointercancel", endDrag);
  };

  const startDrag = (event) => {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    dragging = true;
    frameRect = frame.getBoundingClientRect();
    frame.classList.add("is-dragging");
    queuePosition(pctFromClientX(event.clientX));
    window.addEventListener("pointermove", onPointerMove, { passive: false });
    window.addEventListener("pointerup", endDrag);
    window.addEventListener("pointercancel", endDrag);
    event.preventDefault();
  };

  handle.addEventListener("pointerdown", startDrag);

  frame.addEventListener("pointerdown", (event) => {
    if (handle.contains(event.target)) return;
    startDrag(event);
  });

  handle.addEventListener("keydown", (event) => {
    let next = appState.comparePosition;
    if (event.key === "ArrowLeft" || event.key === "ArrowDown") next -= 4;
    else if (event.key === "ArrowRight" || event.key === "ArrowUp") next += 4;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = 100;
    else return;
    event.preventDefault();
    setComparePosition(next);
  });

  if (typeof ResizeObserver === "function") {
    const ro = new ResizeObserver(() => syncCompareFrameWidth());
    ro.observe(frame);
  } else {
    window.addEventListener("resize", syncCompareFrameWidth, { passive: true });
  }
}

function showGenLoading(title, sub) {
  const overlay = document.getElementById("generationLoadingOverlay");
  const titleEl = document.getElementById("genLoadingTitle");
  const subEl = document.getElementById("genLoadingSub");
  const bgImg = document.getElementById("genLoadingBg");
  const preview = document.getElementById("sourcePhotoPreview");

  if (titleEl && title != null) titleEl.textContent = title;
  if (subEl && sub != null) subEl.textContent = sub;

  if (bgImg) {
    const previewSrc = preview && !preview.classList.contains("is-hidden") ? preview.src : "";
    if (previewSrc) {
      bgImg.src = previewSrc;
      bgImg.classList.remove("is-hidden");
    } else {
      bgImg.removeAttribute("src");
      bgImg.classList.add("is-hidden");
    }
  }

  if (overlay) {
    overlay.classList.remove("is-hidden");
    overlay.setAttribute("aria-hidden", "false");
  }
}

const genLoadingSequence = {
  timers: [],
  active: false,
};

function clearGenLoadingTimers() {
  genLoadingSequence.timers.forEach((id) => clearTimeout(id));
  genLoadingSequence.timers = [];
}

function scheduleGenLoadingStep(fn, delayMs) {
  const id = setTimeout(fn, delayMs);
  genLoadingSequence.timers.push(id);
  return id;
}

function stopGenLoadingSequence() {
  genLoadingSequence.active = false;
  clearGenLoadingTimers();
  hideGenLoading();
}

function startGenLoadingSequence() {
  clearGenLoadingTimers();
  genLoadingSequence.active = true;

  const queueAhead = 3 + Math.floor(Math.random() * 6);
  let remaining = queueAhead;

  const showQueue = () => {
    if (!genLoadingSequence.active) return;
    if (remaining > 0) {
      showGenLoading("Added to queue", `${remaining} people ahead of you.`);
    } else {
      showGenLoading("Added to queue", "You're next…");
    }
  };

  const showSent = () => {
    if (!genLoadingSequence.active) return;
    showGenLoading("Photo sent", "AI is processing your image…");
    scheduleGenLoadingStep(showCreating, 1600);
  };

  const showCreating = () => {
    if (!genLoadingSequence.active) return;
    showGenLoading("Creating…", "Please wait, this may take 1–5 minutes.");
  };

  const tickQueue = () => {
    if (!genLoadingSequence.active) return;
    remaining -= 1;
    if (remaining > 0) {
      showQueue();
      scheduleGenLoadingStep(tickQueue, 750 + Math.floor(Math.random() * 650));
      return;
    }
    showQueue();
    scheduleGenLoadingStep(showSent, 700);
  };

  showQueue();
  scheduleGenLoadingStep(tickQueue, 850 + Math.floor(Math.random() * 500));
}

function finishGenLoadingSequence() {
  return new Promise((resolve) => {
    clearGenLoadingTimers();
    genLoadingSequence.active = false;
    showGenLoading("Created", "Sending to you…");
    scheduleGenLoadingStep(() => {
      hideGenLoading();
      resolve();
    }, 1200);
  });
}

function hideGenLoading() {
  const overlay = document.getElementById("generationLoadingOverlay");
  if (overlay) {
    overlay.classList.add("is-hidden");
    overlay.setAttribute("aria-hidden", "true");
  }
}

function isVideoResultUrl(url) {
  return /\.(mp4|webm|mov)(\?|$)/i.test(String(url || ""));
}

function showGenResult(url, name) {
  const fullUrl = url.startsWith("http") ? url : `${location.origin}${url}`;
  appState.lastResultUrl = fullUrl;
  appState.lastResultName = name || "output";
  const resultCard = document.getElementById("resultCard");
  const empty = document.getElementById("resultEmptyState");
  const wrap = document.getElementById("resultMediaWrap");
  const img = document.getElementById("comfyResultImage");
  const video = document.getElementById("comfyResultVideo");
  const videoWrap = document.getElementById("resultVideoWrap");
  const isVideo = isVideoResultUrl(fullUrl);
  const preview = document.getElementById("sourcePhotoPreview");
  const beforeSrc =
    appState.beforePhotoUrl ||
    (preview && !preview.classList.contains("is-hidden") ? preview.src : "");

  if (resultCard) resultCard.classList.add("is-visible");
  if (empty) empty.style.display = "none";
  if (wrap) wrap.classList.remove("is-hidden");

  if (isVideo && video) {
    hidePhotoCompare();
    if (img) img.classList.add("is-hidden");
    if (videoWrap) videoWrap.classList.remove("is-hidden");
    video.src = fullUrl;
  } else if (beforeSrc) {
    if (videoWrap) videoWrap.classList.add("is-hidden");
    if (video) {
      video.pause();
      video.removeAttribute("src");
      video.load();
    }
    if (img) img.classList.add("is-hidden");
    showPhotoCompare(beforeSrc, fullUrl);
  } else if (img) {
    hidePhotoCompare();
    if (videoWrap) videoWrap.classList.add("is-hidden");
    img.src = fullUrl;
    img.classList.remove("is-hidden");
  }

  requestAnimationFrame(() => {
    const compare = document.getElementById("photoCompareWrap");
    const scrollTarget =
      compare && !compare.classList.contains("is-hidden")
        ? document.getElementById("yourPhotoCard")
        : document.getElementById("resultCard");
    if (scrollTarget) scrollTarget.scrollIntoView({ behavior: "smooth", block: "nearest" });
  });
}

function closeUploadScreen() {
  const uploadPanel = document.querySelector('[data-panel="upload"]');
  const bottomNav = document.querySelector(".bottom-nav");

  uploadPanel.classList.remove("is-active");
  bottomNav.classList.remove("is-hidden");

  if (typeof window.activateBottomView === "function") {
    window.activateBottomView(appState.lastView || "image");
  }
}

function updateComfyStatus(text) {
  const statusEl = document.getElementById("comfyStatusText");
  if (!statusEl) return;
  statusEl.textContent = text || "";
}

function setRunButtonBusy(isBusy) {
  const runBtn = document.getElementById("sendToComfyBtn");
  if (!runBtn) return;
  if (!runBtn.dataset.defaultLabel) {
    runBtn.dataset.defaultLabel = runBtn.textContent || "Generate";
  }

  runBtn.classList.toggle("is-loading", isBusy);
  runBtn.disabled = isBusy;
  runBtn.setAttribute("aria-busy", isBusy ? "true" : "false");
  runBtn.textContent = isBusy ? "Generating…" : runBtn.dataset.defaultLabel;
}

function setupUploadPage() {
  const backBtn = document.getElementById("uploadBackBtn");
  const sourcePhotoInput = document.getElementById("sourcePhotoInput");
  const sourcePhotoPreview = document.getElementById("sourcePhotoPreview");
  const photoDropzone = document.getElementById("photoDropzone");
  const runBtn = document.getElementById("sendToComfyBtn");
  const resultDownloadBtn = document.getElementById("resultDownloadBtn");
  const resultNewBtn = document.getElementById("resultNewBtn");

  backBtn.addEventListener("click", closeUploadScreen);

  sourcePhotoInput.addEventListener("change", () => {
    const file = sourcePhotoInput.files[0];
    if (!file) return;
    if (appState.beforePhotoUrl && appState.beforePhotoUrl.startsWith("blob:")) {
      try {
        URL.revokeObjectURL(appState.beforePhotoUrl);
      } catch {
        /* ignore */
      }
    }
    appState.beforePhotoUrl = URL.createObjectURL(file);
    sourcePhotoPreview.src = appState.beforePhotoUrl;
    sourcePhotoPreview.classList.remove("is-hidden");
    if (photoDropzone) photoDropzone.classList.add("has-photo");
    hidePhotoCompare();
  });

  runBtn.addEventListener("click", runComfyFlow);

  if (resultDownloadBtn) {
    resultDownloadBtn.addEventListener("click", async () => {
      if (appState.lastResultUrl) {
        await downloadGalleryImage(appState.lastResultUrl, appState.lastResultName || "output.png");
      }
    });
  }

  if (resultNewBtn) {
    resultNewBtn.addEventListener("click", () => {
      resetUploadResult();
      updateComfyStatus("");
      const input = document.getElementById("sourcePhotoInput");
      if (input) input.value = "";
      if (sourcePhotoPreview) {
        sourcePhotoPreview.src = "";
        sourcePhotoPreview.classList.add("is-hidden");
      }
      if (photoDropzone) photoDropzone.classList.remove("has-photo");
      if (appState.beforePhotoUrl && appState.beforePhotoUrl.startsWith("blob:")) {
        try {
          URL.revokeObjectURL(appState.beforePhotoUrl);
        } catch {
          /* ignore */
        }
      }
      appState.beforePhotoUrl = "";
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  setupPhotoCompare();
}

function parseErrorDetail(detail) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0] && detail[0].msg) return detail[0].msg;
  return "Request failed";
}

async function runComfyFlowViaBotApi() {
  const sourcePhotoInput = document.getElementById("sourcePhotoInput");
  const file = sourcePhotoInput.files[0];
  if (!file) {
    updateComfyStatus("Please select a photo first.");
    return;
  }
  const initData = getTelegramInitData();
  const mediaType = appState.selectedCard?.type || "image";
  const mediaCategory = appState.selectedCard?.category || "undress";
  const cardPrice = Number(appState.selectedCard?.price || cardPrices.undress);
  if (!initData) {
    updateComfyStatus("Open this mini app from Telegram (missing initData).");
    return;
  }
  if (Number.isFinite(currentDiamondBalance) && currentDiamondBalance < cardPrice) {
    updateComfyStatus(`Not enough diamonds. Required: 💎 ${cardPrice}`);
    redirectToBuy(cardPrice);
    return;
  }
  const fd = new FormData();
  fd.append("image", file, file.name);
  fd.append("init_data", initData);
  fd.append("media_type", mediaType);
  fd.append("media_category", mediaCategory);
  fd.append("card_key", cardKeyFromSrc(appState.selectedCard?.src || ""));
  fd.append("client_price", String(cardPrice));
  if (appState.fromVideoCustomPrompt) {
    const cta = document.getElementById("customVideoPromptInput");
    const customText = cta && typeof cta.value === "string" ? cta.value.trim() : "";
    if (customText) {
      fd.append("prompt", customText);
    }
  }
  try {
    startGenLoadingSequence();
    updateComfyStatus("");
    const res = await fetch("/api/generate", { method: "POST", body: fd });
    const j = await res.json().catch(() => ({}));
    if (!res.ok) {
      stopGenLoadingSequence();
      const msg = parseErrorDetail(j.detail) || `HTTP ${res.status}`;
      if (res.status === 402) {
        updateComfyStatus(`Not enough diamonds. Required: 💎 ${cardPrice}.`);
        redirectToBuy(cardPrice);
      } else {
        updateComfyStatus(`Error: ${msg}`);
      }
      syncDiamondBalance();
      return;
    }
    if (j.files && j.files[0] && j.files[0].url) {
      const f0 = j.files[0];
      await finishGenLoadingSequence();
      showGenResult(f0.url, f0.name || "output");
      updateComfyStatus(j.sent_to_bot ? "Done! Result shown below and sent to bot chat." : "Done! Result shown below.");
      loadGallery();
    } else {
      stopGenLoadingSequence();
      updateComfyStatus("Unexpected response (no output file).");
    }
    if (typeof j.diamonds_after !== "undefined") {
      applyDiamondBalance(j.diamonds_after);
    } else {
      syncDiamondBalance();
    }
  } catch (error) {
    stopGenLoadingSequence();
    updateComfyStatus(`Error: ${error.message || error}`);
  }
}

function setupLazyVideoPreviews() {
  if (videoPreviewState.observer) return;
  videoPreviewState.observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        const video = entry.target;
        if (!(video instanceof HTMLVideoElement)) return;
        const card = video.closest(".media-card--video, .custom-video-hero");
        if (!card || card.dataset.previewMode === "gif") return;
        if (entry.isIntersecting) {
          card.classList.add("preview-mode-mp4");
          ensureVideoSource(video, false);
          queueVideoPlay(video);
        } else {
          pauseVideoPreview(video);
        }
      });
    },
    { root: null, rootMargin: "280px 0px", threshold: 0.05 }
  );
}

function ensureVideoSource(video, eager = false) {
  if (video.dataset.loaded === "1") return;
  const src = video.dataset.src;
  if (!src) return;
  video.preload = eager ? "auto" : "metadata";
  video.src = src;
  video.load();
  video.dataset.loaded = "1";
}

function queueVideoPlay(video) {
  const card = video.closest(".media-card--video, .custom-video-hero");
  if (card && card.dataset.previewMode === "gif") return;

  if (videoPreviewState.playing.has(video) && !video.paused) return;

  const markReady = () => {
    video.classList.add("is-ready");
    if (card) card.classList.add("preview-mode-mp4");
  };

  const startPlay = () => {
    markReady();
    while (videoPreviewState.playing.size >= videoPreviewState.maxConcurrent) {
      pauseVideoPreview(videoPreviewState.playing.values().next().value);
    }
    try {
      video.muted = true;
      video.playsInline = true;
      const p = video.play();
      const onPlaying = () => {
        videoPreviewState.playing.add(video);
        video.classList.add("is-active");
      };
      if (p && typeof p.then === "function") {
        p.then(onPlaying).catch(() => {
          markReady();
        });
      } else {
        onPlaying();
      }
    } catch {
      markReady();
    }
  };

  if (video.readyState >= 2) {
    startPlay();
    return;
  }

  if (video.dataset.playPending === "1") return;
  video.dataset.playPending = "1";
  const onReady = () => {
    video.removeEventListener("canplay", onReady);
    video.removeEventListener("loadeddata", onReady);
    delete video.dataset.playPending;
    startPlay();
  };
  video.addEventListener("canplay", onReady, { once: true });
  video.addEventListener("loadeddata", onReady, { once: true });
}

function pauseVideoPreview(video) {
  if (!(video instanceof HTMLVideoElement)) return;
  try {
    video.pause();
  } catch {
    /* ignore */
  }
  delete video.dataset.playPending;
  videoPreviewState.playing.delete(video);
}

function pauseAllVideoPreviews() {
  document.querySelectorAll("video.preview-video").forEach((videoEl) => {
    pauseVideoPreview(videoEl);
  });
}

function observeVideoPreviews(root) {
  setupLazyVideoPreviews();
  const scope = root || document;
  scope.querySelectorAll("video.preview-video").forEach((videoEl) => {
    if (videoEl.dataset.observed === "1") return;
    videoEl.dataset.observed = "1";
    videoPreviewState.observer.observe(videoEl);
  });
}

async function runComfyFlow() {
  try {
    setRunButtonBusy(true);

    if (getTelegramInitData()) {
      await runComfyFlowViaBotApi();
      return;
    }

    updateComfyStatus("Open this mini app from Telegram to generate.");
  } finally {
    setRunButtonBusy(false);
  }
}

async function bootApp() {
  initLanguageSystem();
  await getMiniappConfig();
  renderVideoCards("videoPresetsGrid", videoPresetFiles);
  renderCustomPromptPanel();
  setupVideoTabs();
  setupTabs();
  setupCardActions();
  setupStoreModal();
  setupUploadPage();
  setupGalleryActions();
  setupVideoScrollRefresh();
  updateCardLocks();

  if (typeof requestIdleCallback === "function") {
    requestIdleCallback(prefetchGifPreviews, { timeout: 2000 });
  } else {
    setTimeout(prefetchGifPreviews, 1200);
  }

  initTelegramWebApp();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bootApp);
} else {
  bootApp();
}
