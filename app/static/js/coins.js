// 六爻摇卦：每次点击掷三枚铜钱。背面 = 3，字面 = 2，三枚相加得 6/7/8/9。
// 随机数来自浏览器的 crypto.getRandomValues（密码学级随机）。
(function () {
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function coinFlip() {
    const a = new Uint8Array(1);
    crypto.getRandomValues(a);
    return a[0] % 2 === 0 ? 3 : 2; // 3=背 2=字
  }

  document.querySelectorAll("[data-coin-widget]").forEach(function (w) {
    const coins = w.querySelectorAll(".coin");
    const btn = w.querySelector("[data-toss]");
    const status = w.querySelector("[data-status]");
    const msg = function (k, n) { return (status.dataset["msg" + k] || "").replace(/\{n\}/g, n); };
    const lines = w.querySelector("[data-lines]");
    const hidden = w.querySelector("[data-tosses]");
    const clientTime = w.querySelector("[data-client-time]");
    const form = w.closest("form");
    const submit = form && form.querySelector("[data-after-toss]");
    const tosses = [];
    if (submit) submit.disabled = true;

    function stamp() { // 记录起卦时你所在地的本地时间
      const d = new Date(), z = function (n) { return String(n).padStart(2, "0"); };
      clientTime.value = d.getFullYear() + "-" + z(d.getMonth() + 1) + "-" + z(d.getDate()) + "T" + z(d.getHours()) + ":" + z(d.getMinutes());
    }
    stamp();

    function drawLine(v) {
      const el = document.createElement("div");
      el.className = "yao-line" + (v === 6 || v === 8 ? " yin" : "") + (v === 6 || v === 9 ? " moving" : "");
      lines.insertBefore(el, lines.firstChild); // 卦从下往上长
    }

    btn.addEventListener("click", function () {
      if (tosses.length >= 6) return;
      btn.disabled = true;
      const faces = [coinFlip(), coinFlip(), coinFlip()];
      coins.forEach(function (c, i) {
        c.classList.remove("spin", "flip-back");
        void c.offsetWidth;
        if (!reduce) c.classList.add("spin");
        setTimeout(function () { c.classList.remove("spin"); if (faces[i] === 3) c.classList.add("flip-back"); }, reduce ? 0 : 900);
      });
      setTimeout(function () {
        const v = faces.reduce(function (a, b) { return a + b; }, 0);
        tosses.push(v);
        drawLine(v);
        if (tosses.length < 6) {
          status.textContent = msg("Next", tosses.length + 1);
          btn.textContent = msg("Btn", tosses.length + 1);
          btn.disabled = false;
        } else {
          status.textContent = msg("Done");
          btn.textContent = msg("Finished");
          hidden.value = tosses.join(",");
          stamp();
          if (submit) { submit.disabled = false; submit.focus(); }
        }
      }, reduce ? 50 : 950);
    });

    // 手动录入
    const manual = w.querySelectorAll("[data-manual]");
    manual.forEach(function (s) {
      s.addEventListener("change", function () {
        const vals = Array.from(manual).map(function (m) { return m.value; });
        if (vals.every(Boolean)) {
          hidden.value = vals.join(",");
          stamp();
          lines.innerHTML = "";
          vals.forEach(function (v) { drawLine(parseInt(v, 10)); });
          status.textContent = msg("Manual");
          if (submit) submit.disabled = false;
        }
      });
    });
  });
})();
