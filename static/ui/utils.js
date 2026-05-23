export function el(id) {
  return document.getElementById(id);
}

export function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = String(s == null ? "" : s);
  return d.innerHTML;
}

export function showToast(message, type = "info") {
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    container.style.cssText = "position: fixed; top: 20px; left: 50%; transform: translateX(-50%); z-index: 9999; display: flex; flex-direction: column; gap: 10px; pointer-events: none;";
    document.body.appendChild(container);
  }

  const toast = document.createElement("div");
  const bgColor = type === "error" ? "rgba(255, 80, 80, 0.9)" : "rgba(40, 40, 40, 0.9)";
  toast.style.cssText = `background: ${bgColor}; color: white; padding: 10px 20px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); font-size: 14px; animation: slideDown 0.3s ease forwards; max-width: 80vw; word-break: break-word; text-align: center;`;
  toast.textContent = message;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = "slideUp 0.3s ease forwards";
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

// Add keyframes for toast animation if not exists
if (!document.getElementById("toast-keyframes")) {
  const style = document.createElement("style");
  style.id = "toast-keyframes";
  style.textContent = `
    @keyframes slideDown { from { transform: translateY(-20px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
    @keyframes slideUp { from { transform: translateY(0); opacity: 1; } to { transform: translateY(-20px); opacity: 0; } }
  `;
  document.head.appendChild(style);
}
