window.App = window.App || {};

(function(App) {
  "use strict";

  var HtmlUtils = {
    escape(text) {
      if (!text) return '';
      var str = String(text);
      var div = document.createElement('div');
      div.textContent = str;
      return div.innerHTML.replace(/'/g, '&#39;');
    },

    setSafeHtml(element, html) {
      if (element) {
        element.innerHTML = this.escape(html);
      }
    },

    setTrustedHtml(element, html) {
      if (element) {
        element.innerHTML = html;
      }
    },

    _ALLOWED_TAGS: new Set(['b', 'i', 'u', 'strong', 'em', 'br']),

    sanitize(text) {
      if (!text) return '';
      var escaped = String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
      escaped = escaped.replace(/&lt;(\/?)(b|i|u|strong|em|br)\s*\/?&gt;/gi, function(match, slash, tag) {
        tag = tag.toLowerCase();
        if (HtmlUtils._ALLOWED_TAGS.has(tag)) {
          if (tag === 'br') return '<br>';
          return '<' + slash + tag + '>';
        }
        return match;
      });
      return escaped;
    },
  };

  App.HtmlUtils = HtmlUtils;

})(window.App);
