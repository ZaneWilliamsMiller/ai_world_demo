// ═══════════════════════════════════════════════════════
//  llm-test.js — LLM 连接测试模块
// ═══════════════════════════════════════════════════════
window.App = window.App || {};

(function(App) {
  "use strict";

  /**
   * 测试 LLM API 连接
   * 返回 { ok, latency, message, response? }
   */
  App.testLlmConnection = async function() {
    var startTime = Date.now();
    var resultEl = document.getElementById("llmTestResult");
    if (resultEl) {
      resultEl.textContent = "\u6d4b\u8bd5\u4e2d...";
      resultEl.className = "test-result testing";
    }

    try {
      var res = await fetch(App.LLM_API_URL + "/chat/completions", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": "Bearer " + App.LLM_API_KEY
        },
        body: JSON.stringify({
          model: App.LLM_MODEL,
          messages: [
            { role: "system", content: "\u4f60\u662f\u4e00\u4e2a\u6d4b\u8bd5\u52a9\u624b\u3002\u8bf7\u7528\u4e00\u53e5\u8bdd\u56de\u590d\u3002" },
            { role: "user", content: "\u8bf4\u4e00\u53e5\u6c5f\u6e56\u8bdd" }
          ],
          max_tokens: 50,
          stream: false
        }),
        signal: AbortSignal.timeout(15000)
      });

      var latency = Date.now() - startTime;

      if (!res.ok) {
        var errText = await res.text();
        var msg = "LLM API \u8fde\u63a5\u5931\u8d25 (" + res.status + "): " + errText.slice(0, 200);
        if (resultEl) {
          resultEl.textContent = msg;
          resultEl.className = "test-result fail";
        }
        return { ok: false, latency: latency, message: msg };
      }

      var data = await res.json();
      var reply = data.choices && data.choices[0] && data.choices[0].message
        ? data.choices[0].message.content : "(无回复)";

      var msg = "\u8fde\u63a5\u6210\u529f! \u5ef6\u8fdf: " + latency + "ms | \u56de\u590d: " + reply;
      if (resultEl) {
        resultEl.textContent = msg;
        resultEl.className = "test-result success";
      }
      return { ok: true, latency: latency, message: msg, response: reply };

    } catch (e) {
      var latency2 = Date.now() - startTime;
      var msg2 = "\u8fde\u63a5\u5931\u8d25: " + e.message;
      if (resultEl) {
        resultEl.textContent = msg2;
        resultEl.className = "test-result fail";
      }
      return { ok: false, latency: latency2, message: msg2 };
    }
  };

  /**
   * 测试后端 API 连接
   */
  App.testBackendConnection = async function() {
    var resultEl = document.getElementById("backendTestResult");
    if (resultEl) {
      resultEl.textContent = "\u6d4b\u8bd5\u4e2d...";
      resultEl.className = "test-result testing";
    }

    var startTime = Date.now();
    try {
      var result = await App.checkBackend();
      var latency = Date.now() - startTime;

      if (result.ok) {
        var msg = "\u540e\u7aef\u8fde\u63a5\u6210\u529f! \u5ef6\u8fdf: " + latency + "ms";
        if (resultEl) {
          resultEl.textContent = msg;
          resultEl.className = "test-result success";
        }
        return { ok: true, latency: latency, message: msg };
      } else {
        var msg2 = "\u540e\u7aef\u8fde\u63a5\u5931\u8d25" + (result.status ? " (" + result.status + ")" : "") + ": " + (result.error || "");
        if (resultEl) {
          resultEl.textContent = msg2;
          resultEl.className = "test-result fail";
        }
        return { ok: false, latency: latency, message: msg2 };
      }
    } catch (e) {
      var latency2 = Date.now() - startTime;
      var msg3 = "\u8fde\u63a5\u5931\u8d25: " + e.message;
      if (resultEl) {
        resultEl.textContent = msg3;
        resultEl.className = "test-result fail";
      }
      return { ok: false, latency: latency2, message: msg3 };
    }
  };

})(window.App);
