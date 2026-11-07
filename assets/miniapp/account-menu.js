(function () {
  "use strict";

  var menu;
  var dialog;
  var trigger;
  var account;
  var accountRequest;
  var accountState = "unknown";
  var previousFocus;
  var style = document.createElement("style");
  var balanceCacheKey = "undress-miniapp-credit-balance";

  function readCachedBalance() {
    try {
      var cached = JSON.parse(window.sessionStorage.getItem(balanceCacheKey) || "null");
      if (cached && Number.isFinite(cached.value) && cached.value >= 0 &&
          Date.now() - cached.savedAt < 30 * 60 * 1000) {
        return cached.value;
      }
    } catch (_) {
      // Storage may be unavailable in private browsing contexts.
    }
    return null;
  }

  style.textContent = [
    "@keyframes miniapp-account-menu-enter{from{opacity:0;transform:translateY(-5px) scale(.985)}to{opacity:1;transform:translateY(0) scale(1)}}",
    "@keyframes miniapp-account-menu-exit{to{opacity:0;transform:translateY(-3px) scale(.99)}}",
    "@keyframes miniapp-account-overlay-enter{from{opacity:0}to{opacity:1}}",
    "@keyframes miniapp-account-overlay-exit{to{opacity:0}}",
    "@keyframes miniapp-account-dialog-enter{from{opacity:0;transform:translateY(7px) scale(.99)}to{opacity:1;transform:translateY(0) scale(1)}}",
    "@keyframes miniapp-account-dialog-exit{to{opacity:0;transform:translateY(4px) scale(.99)}}",
    ".miniapp-account-menu{position:fixed;z-index:2147483000;width:min(264px,calc(100vw - 24px));padding:8px;border:1px solid rgba(255,255,255,.09);border-radius:20px;background:#111;box-shadow:0 16px 48px rgba(0,0,0,.5);color:#fff;font:inherit;transform-origin:top right;animation:miniapp-account-menu-enter 170ms cubic-bezier(.2,.75,.25,1) both}",
    ".miniapp-account-menu.is-closing{pointer-events:none;animation:miniapp-account-menu-exit 120ms ease both}",
    ".miniapp-account-row{display:flex;width:100%;align-items:center;gap:12px;border:1px solid rgba(255,255,255,.06);border-radius:16px;padding:10px;background:rgba(255,255,255,.015);color:inherit;text-align:left;cursor:pointer;transition:background 140ms ease,border-color 140ms ease,transform 140ms ease}",
    ".miniapp-account-row:hover,.miniapp-account-row:focus-visible{background:rgba(255,255,255,.06);border-color:rgba(255,255,255,.12);transform:translateY(-1px);outline:none}",
    ".miniapp-account-avatar{display:grid;width:44px;height:44px;flex:none;place-items:center;overflow:hidden;border-radius:50%;background:#242424;color:#aaa;font-size:19px;font-weight:700}",
    ".miniapp-account-avatar img{width:100%;height:100%;object-fit:cover}",
    ".miniapp-account-copy{min-width:0;flex:1}",
    ".miniapp-account-title{display:block;font-size:16px;font-weight:700}",
    ".miniapp-account-subtitle{display:block;overflow:hidden;margin-top:3px;color:rgba(255,255,255,.75);font-size:12px;text-overflow:ellipsis;white-space:nowrap}",
    ".miniapp-account-chevron{flex:none;color:rgba(255,255,255,.55);font-size:22px;line-height:1}",
    ".miniapp-account-status{margin:8px 8px 2px;color:#ffbd7c;font:12px/1.4 Arial,sans-serif}",
    ".miniapp-account-overlay{position:fixed;z-index:2147483001;inset:0;display:grid;place-items:center;padding:20px;background:rgba(0,0,0,.72);backdrop-filter:blur(7px);font:14px/1.5 Arial,sans-serif;color:#f5f5f5;animation:miniapp-account-overlay-enter 180ms ease both}",
    ".miniapp-account-overlay.is-closing{pointer-events:none;animation:miniapp-account-overlay-exit 140ms ease both}",
    ".miniapp-account-dialog{width:min(440px,100%);max-height:calc(100vh - 40px);overflow:auto;border:1px solid rgba(255,255,255,.12);border-radius:22px;padding:22px;background:#111;box-shadow:0 24px 80px rgba(0,0,0,.55);animation:miniapp-account-dialog-enter 200ms cubic-bezier(.2,.75,.25,1) both}",
    ".miniapp-account-overlay.is-closing .miniapp-account-dialog{animation:miniapp-account-dialog-exit 140ms ease both}",
    ".miniapp-account-dialog-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:18px}",
    ".miniapp-account-dialog-head h2{margin:0;font-size:20px}",
    ".miniapp-account-close{width:36px;height:36px;border:0;border-radius:50%;background:#ffffff12;color:#fff;font-size:22px;cursor:pointer}",
    ".miniapp-account-profile{display:flex;align-items:center;gap:14px;margin-bottom:18px;border:1px solid #ffffff12;border-radius:16px;padding:14px;background:#ffffff05}",
    ".miniapp-account-profile .miniapp-account-avatar{width:56px;height:56px;font-size:22px}",
    ".miniapp-account-name{overflow-wrap:anywhere;font-size:16px;font-weight:700}",
    ".miniapp-account-email{overflow-wrap:anywhere;color:#aaa;font-size:13px}",
    ".miniapp-account-details{margin:0;border-top:1px solid #ffffff12}",
    ".miniapp-account-detail{display:flex;justify-content:space-between;gap:16px;border-bottom:1px solid #ffffff12;padding:11px 0}",
    ".miniapp-account-detail dt{color:#999}",
    ".miniapp-account-detail dd{margin:0;color:#f5f5f5;font-weight:650;text-align:right;overflow-wrap:anywhere}",
    ".miniapp-account-dialog-status{min-height:18px;margin:10px 0 0;color:#ffbd7c;font-size:12px;text-align:center}",
    ".miniapp-account-signout{width:100%;margin-top:14px;border:1px solid #ffffff1f;border-radius:12px;padding:11px;background:#ffffff08;color:#f1f1f1;font:inherit;font-weight:650;cursor:pointer}",
    ".miniapp-account-signout:hover{background:#ffffff12}",
    "@media(max-width:520px){.miniapp-account-dialog{padding:18px}}",
    "@media(prefers-reduced-motion:reduce){.miniapp-account-menu,.miniapp-account-overlay,.miniapp-account-dialog,.miniapp-account-row{animation:none!important;transition:none!important}}"
  ].join("");
  document.head.appendChild(style);

  function element(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function setAccountAvatar(container, profile, fallback) {
    container.replaceChildren();
    var imageUrl = profile && typeof profile.photo_url === "string" ? profile.photo_url : "";
    if (imageUrl) {
      var image = document.createElement("img");
      image.alt = "";
      image.referrerPolicy = "no-referrer";
      image.src = imageUrl;
      container.appendChild(image);
      return;
    }
    container.textContent = fallback;
  }

  function setCreditBalance(value) {
    var balance = Number(value);
    if (!Number.isFinite(balance) || balance < 0) return;

    try {
      window.sessionStorage.setItem(balanceCacheKey, JSON.stringify({ value: balance, savedAt: Date.now() }));
    } catch (_) {
      // Balance display still works when storage is unavailable.
    }

    var formatted = balance.toLocaleString(undefined, {
      maximumFractionDigits: 2
    });
    document.querySelectorAll("button number-flow-react, button [data-credit-balance]").forEach(function (counter) {
      var display = counter;
      if (counter.tagName.toLowerCase() === "number-flow-react") {
        display = element("span");
        display.setAttribute("data-credit-balance", "");
        display.style.cssText = "display:inline-block;direction:ltr;white-space:nowrap;line-height:1";
        counter.replaceWith(display);
      }
      display.textContent = formatted;
      display.setAttribute("aria-label", formatted + " credits");
    });

    if (account) account.diamonds = balance;
  }

  var cachedBalance = readCachedBalance();
  if (cachedBalance !== null) setCreditBalance(cachedBalance);

  function readAccount() {
    if (accountRequest) return accountRequest;

    accountState = "loading";
    accountRequest = fetch("/api/auth/session", { credentials: "same-origin", cache: "no-store" })
      .then(function (response) {
        if (response.status === 401) return null;
        if (!response.ok) throw new Error("Could not load your account session.");
        return response.json();
      })
      .then(function (session) {
        if (!session) {
          account = null;
          accountState = "anonymous";
          return null;
        }
        return fetch("/api/miniapp/profile", {
          method: "POST",
          credentials: "same-origin",
          cache: "no-store",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({})
        }).then(function (response) {
          if (!response.ok) throw new Error("Could not load your account details.");
          return response.json();
        }).then(function (profile) {
          account = Object.assign({}, session, profile);
          accountState = "signed-in";
          return account;
        });
      })
      .catch(function (error) {
        account = null;
        accountState = "error";
        throw error;
      })
      .then(function (result) {
        accountRequest = null;
        return result;
      }, function (error) {
        accountRequest = null;
        throw error;
      });

    return accountRequest;
  }

  readAccount().then(function (profile) {
    if (profile && profile.diamonds !== undefined && profile.diamonds !== null) {
      setCreditBalance(profile.diamonds);
    }
  }).catch(function (error) {
    window.console.error("Unable to load credit balance:", error);
  });

  window.addEventListener("undress:balance-updated", function (event) {
    if (event.detail && event.detail.diamonds !== undefined) {
      setCreditBalance(event.detail.diamonds);
    }
  });

  function navigateToLogin() {
    var destination = "/login.html?next=%2FImage.html";
    try {
      window.top.location.assign(destination);
    } catch (error) {
      window.location.assign(destination);
    }
  }

  function closeMenu() {
    var closingMenu = menu;
    menu = null;
    if (trigger) trigger.setAttribute("aria-expanded", "false");
    if (!closingMenu) return;
    closingMenu.setAttribute("aria-hidden", "true");
    closingMenu.classList.add("is-closing");
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      closingMenu.remove();
      return;
    }
    window.setTimeout(function () {
      if (closingMenu.parentNode) closingMenu.remove();
    }, 130);
  }

  function closeDialog() {
    var closingDialog = dialog;
    dialog = null;
    if (closingDialog) {
      closingDialog.setAttribute("aria-hidden", "true");
      closingDialog.classList.add("is-closing");
      if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        closingDialog.remove();
      } else {
        window.setTimeout(function () {
          if (closingDialog.parentNode) closingDialog.remove();
        }, 150);
      }
    }
    if (previousFocus && document.contains(previousFocus)) previousFocus.focus();
    previousFocus = null;
  }

  function detailRow(list, label, value) {
    var row = element("div", "miniapp-account-detail");
    var term = element("dt", "", label);
    var description = element("dd", "", value);
    row.appendChild(term);
    row.appendChild(description);
    list.appendChild(row);
  }

  function showAccountDialog(profile) {
    closeMenu();
    closeDialog();
    previousFocus = trigger;

    var overlay = element("div", "miniapp-account-overlay");
    overlay.setAttribute("role", "presentation");
    var panel = element("section", "miniapp-account-dialog");
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-modal", "true");
    panel.setAttribute("aria-labelledby", "miniapp-account-dialog-title");

    var heading = element("div", "miniapp-account-dialog-head");
    var title = element("h2", "", "Account");
    title.id = "miniapp-account-dialog-title";
    var closeButton = element("button", "miniapp-account-close", "×");
    closeButton.type = "button";
    closeButton.setAttribute("aria-label", "Close account details");
    closeButton.addEventListener("click", closeDialog);
    heading.appendChild(title);
    heading.appendChild(closeButton);

    var profileCard = element("div", "miniapp-account-profile");
    var avatar = element("div", "miniapp-account-avatar");
    setAccountAvatar(avatar, profile, "U");
    var identity = document.createElement("div");
    var name = element("div", "miniapp-account-name", profile.display_name || profile.first_name || "Google user");
    var email = element("div", "miniapp-account-email", profile.email || "");
    identity.appendChild(name);
    identity.appendChild(email);
    profileCard.appendChild(avatar);
    profileCard.appendChild(identity);

    var details = element("dl", "miniapp-account-details");
    var membership = profile.membership || {};
    var expiry = membership.expires_at ? new Date(membership.expires_at) : null;
    var expiryText = expiry && !Number.isNaN(expiry.getTime())
      ? expiry.toLocaleDateString()
      : "No active subscription";
    detailRow(details, "Account ID", String(profile.user_id || "—"));
    detailRow(details, "Sign-in", (profile.provider || "google").toUpperCase());
    detailRow(details, "Plan", membership.plan || "Free");
    detailRow(details, "Renewal / expiry", expiryText);
    detailRow(details, "Available credits", Number(profile.diamonds || 0).toLocaleString(undefined, {
      maximumFractionDigits: 2
    }));

    var status = element("p", "miniapp-account-dialog-status");
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    var signOut = element("button", "miniapp-account-signout", "Sign out");
    signOut.type = "button";
    signOut.addEventListener("click", function () {
      signOut.disabled = true;
      status.textContent = "Signing out…";
      fetch("/api/auth/logout", {
        method: "POST",
        credentials: "same-origin"
      }).then(function (response) {
        if (!response.ok) throw new Error("Sign out failed. Please try again.");
        closeDialog();
        navigateToLogin();
      }).catch(function (error) {
        signOut.disabled = false;
        status.textContent = error.message;
      });
    });

    panel.appendChild(heading);
    panel.appendChild(profileCard);
    panel.appendChild(details);
    panel.appendChild(status);
    panel.appendChild(signOut);
    overlay.appendChild(panel);
    overlay.addEventListener("click", function (event) {
      if (event.target === overlay) closeDialog();
    });
    document.body.appendChild(overlay);
    dialog = overlay;
    closeButton.focus();
  }

  function openAccountDialog() {
    closeMenu();
    return readAccount().then(function (profile) {
      if (!profile) {
        navigateToLogin();
        return;
      }
      showAccountDialog(profile);
    }).catch(function (error) {
      window.console.error("Unable to load account details:", error);
    });
  }

  function openMenu(button) {
    trigger = button;
    button.setAttribute("aria-expanded", "true");
    menu = element("div", "miniapp-account-menu");
    menu.setAttribute("role", "menu");
    var row = element("button", "miniapp-account-row");
    row.type = "button";
    row.setAttribute("role", "menuitem");
    var avatar = element("div", "miniapp-account-avatar", "U");
    var copy = element("span", "miniapp-account-copy");
    var title = element("span", "miniapp-account-title", "Account");
    var subtitle = element("span", "miniapp-account-subtitle", "Loading account…");
    copy.appendChild(title);
    copy.appendChild(subtitle);
    var chevron = element("span", "miniapp-account-chevron", "›");
    chevron.setAttribute("aria-hidden", "true");
    row.appendChild(avatar);
    row.appendChild(copy);
    row.appendChild(chevron);
    menu.appendChild(row);

    var rect = button.getBoundingClientRect();
    menu.style.top = Math.min(rect.bottom + 8, window.innerHeight - 80) + "px";
    menu.style.right = Math.max(12, window.innerWidth - rect.right) + "px";
    document.body.appendChild(menu);

    row.addEventListener("click", function () {
      if (accountState === "loading" && accountRequest) {
        row.disabled = true;
        accountRequest.then(function (profile) {
          row.disabled = false;
          if (!profile) {
            closeMenu();
            navigateToLogin();
            return;
          }
          showAccountDialog(profile);
        }).catch(function (error) {
          row.disabled = false;
          subtitle.textContent = error.message;
        });
        return;
      }
      if (accountState === "signed-in" && account) {
        showAccountDialog(account);
        return;
      }
      if (accountState === "anonymous") {
        closeMenu();
        navigateToLogin();
        return;
      }
      readAccount().then(function (profile) {
        if (profile) showAccountDialog(profile);
        else {
          closeMenu();
          navigateToLogin();
        }
      }).catch(function (error) {
        subtitle.textContent = error.message;
      });
    });

    readAccount().then(function (profile) {
      if (!menu || !menu.isConnected) return;
      if (!profile) {
        setAccountAvatar(avatar, null, "U");
        subtitle.textContent = "Anonymous";
        return;
      }
      setAccountAvatar(avatar, profile, (profile.display_name || profile.first_name || "U").slice(0, 1).toUpperCase());
      subtitle.textContent = profile.display_name || profile.email || "Signed in";
    }).catch(function (error) {
      if (menu && menu.isConnected) subtitle.textContent = "Unable to load account";
      window.console.error("Unable to load account menu:", error);
    });
  }

  window.addEventListener("click", function (event) {
    var button = null;
    var path = typeof event.composedPath === "function" ? event.composedPath() : [];

    function isCreditButton(node) {
      if (!node || node.tagName !== "BUTTON" ||
          !node.querySelector("number-flow-react, [data-credit-balance]")) {
        return false;
      }
      var plusPaths = node.querySelectorAll("svg path[d]");
      for (var pathIndex = 0; pathIndex < plusPaths.length; pathIndex += 1) {
        if ((plusPaths[pathIndex].getAttribute("d") || "").indexOf("M12 4.5v15m7.5-7.5h-") === 0) {
          return true;
        }
      }
      return false;
    }

    for (var index = 0; index < path.length; index += 1) {
      if (isCreditButton(path[index])) {
        button = path[index];
        break;
      }
    }

    if (!button) {
      var target = event.target;
      var candidate = target && target.closest ? target.closest("button") : null;
      if (isCreditButton(candidate)) button = candidate;
    }

    if (!button) return;

    event.preventDefault();
    event.stopImmediatePropagation();

    try {
      var router = window.parent && window.parent.__miniappRouter;
      if (router && typeof router.navigate === "function" && router.navigate("/creator.html")) {
        return;
      }
    } catch (error) {
      // Fall through to a direct route when the miniapp router is unavailable.
    }
    window.location.assign("/creator.html");
  }, true);

  document.addEventListener("click", function (event) {
    var button = event.target && event.target.closest
      ? event.target.closest("header button[aria-expanded]")
      : null;

    if (button) {
      event.preventDefault();
      event.stopImmediatePropagation();
      if (menu) closeMenu();
      else openMenu(button);
      return;
    }

    if (menu && !menu.contains(event.target)) closeMenu();
  }, true);

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      if (dialog) closeDialog();
      else closeMenu();
    }
  });

  window.__openAccountDialog = openAccountDialog;
})();
