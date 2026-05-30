window.App = window.App || {};

(function(App) {
  "use strict";

  var stats = { total: 0, running: 0, success: 0, error: 0 };
  var verbose = false;
  var modules = [];
  var testResults = {};

  var interactiveVerbose = false;
  var interactiveModules = [];
  var interactiveResults = {};
  var interactiveStats = { success: 0, failed: 0 };

  function apiBase() {
    return "/api";
  }

  function safeId(name) {
    return name.replace(/[\/\\\.]/g, '_');
  }

  function switchTab(tab) {
    var funcPanel = document.getElementById('functionalPanel');
    var intPanel = document.getElementById('interactivePanel');
    var tabFunc = document.getElementById('tabFunctional');
    var tabInt = document.getElementById('tabInteractive');

    if (tab === 'functional') {
      funcPanel.style.display = '';
      intPanel.style.display = 'none';
      tabFunc.classList.add('active');
      tabInt.classList.remove('active');
    } else {
      funcPanel.style.display = 'none';
      intPanel.style.display = '';
      tabFunc.classList.remove('active');
      tabInt.classList.add('active');
      if (interactiveModules.length === 0) {
        loadInteractiveModules();
      }
    }
  }

  async function loadModules() {
    try {
      var resp = await fetch(apiBase() + '/tests/modules');

      if (resp.status === 404) {
        showError('\u274c \u6d4b\u8bd5\u8def\u7531\u672a\u542f\u7528',
          '\u8bf7\u5728 .env \u4e2d\u8bbe\u7f6e ENABLE_TEST_ROUTES=1 \u540e\u91cd\u542f\u670d\u52a1');
        return;
      }
      if (resp.status === 403) {
        showError('\u274c \u6d4b\u8bd5\u8def\u7531\u5df2\u7981\u7528',
          '\u8bf7\u5728 .env \u4e2d\u8bbe\u7f6e ENABLE_TEST_ROUTES=1 \u540e\u91cd\u542f\u670d\u52a1');
        return;
      }

      var data = await resp.json();
      modules = data.modules;

      document.getElementById('totalTests').textContent = data.count;
      stats.total = data.count;

      renderModules();

    } catch (err) {
      console.error('Failed to load modules:', err);
      showError('\u274c \u65e0\u6cd5\u8fde\u63a5\u5230\u540e\u7aef\u670d\u52a1',
        '\u8bf7\u786e\u4fdd\u540e\u7aef\u5df2\u5728\u8fd0\u884c (python start.py)');
    }
  }

  async function loadInteractiveModules() {
    try {
      var resp = await fetch(apiBase() + '/tests/interactive/modules');
      if (!resp.ok) {
        document.getElementById('interactiveModuleList').innerHTML =
          '<div style="text-align:center;padding:40px;color:#ff4757;">\u274c \u65e0\u6cd5\u52a0\u8f7d\u4ea4\u4e92\u6d4b\u8bd5\u6a21\u5757</div>';
        return;
      }
      var data = await resp.json();
      interactiveModules = data.modules;
      document.getElementById('interactiveTotal').textContent = data.count;
      renderInteractiveModules();
    } catch (err) {
      console.error('Failed to load interactive modules:', err);
      document.getElementById('interactiveModuleList').innerHTML =
        '<div style="text-align:center;padding:40px;color:#ff4757;">\u274c \u8fde\u63a5\u5931\u8d25</div>';
    }
  }

  function showError(title, subtitle) {
    var container = document.getElementById('moduleList');
    container.innerHTML = '';
    var errDiv = document.createElement('div');
    errDiv.style.cssText = 'text-align:center;padding:40px;color:#ff4757;';
    errDiv.textContent = title;
    var small = document.createElement('small');
    small.style.cssText = 'color:#a0a0b0;';
    small.textContent = subtitle;
    errDiv.appendChild(document.createElement('br'));
    errDiv.appendChild(small);
    container.appendChild(errDiv);
  }

  function renderModules() {
    var container = document.getElementById('moduleList');
    container.innerHTML = '';

    modules.forEach(function(mod) {
      var section = createModuleSection(mod, false);
      container.appendChild(section);
    });
  }

  function createModuleSection(mod, isInteractive) {
    var section = document.createElement('div');
    section.className = 'module-section';
    section.id = (isInteractive ? 'imod-' : 'module-') + safeId(mod.id);

    var header = document.createElement('div');
    header.className = 'module-header';

    var leftDiv = document.createElement('div');
    leftDiv.className = 'module-header-left';

    var expandBtn = document.createElement('button');
    expandBtn.className = 'expand-btn';
    expandBtn.textContent = '\u25b6';
    expandBtn.addEventListener('click', function() {
      toggleModule(mod.id, expandBtn, isInteractive);
    });
    leftDiv.appendChild(expandBtn);

    var iconSpan = document.createElement('span');
    iconSpan.className = 'module-icon';
    iconSpan.textContent = isInteractive ? (mod.icon || '\ud83e\udde0') : getModuleIcon(mod.id);
    leftDiv.appendChild(iconSpan);

    var titleDiv = document.createElement('div');
    titleDiv.className = 'module-title';

    var nameSpan = document.createElement('span');
    nameSpan.className = 'module-name';
    nameSpan.textContent = mod.label;
    titleDiv.appendChild(nameSpan);

    var countSpan = document.createElement('span');
    countSpan.className = 'module-count';
    countSpan.textContent = mod.count + ' \u4e2a\u6d4b\u8bd5';
    titleDiv.appendChild(countSpan);

    var badge = document.createElement('span');
    badge.className = 'module-badge';
    badge.id = (isInteractive ? 'ibadge-' : 'badge-') + safeId(mod.id);
    badge.textContent = '\u23f3 \u5f85\u6d4b';
    titleDiv.appendChild(badge);

    leftDiv.appendChild(titleDiv);
    header.appendChild(leftDiv);

    var runBtn = document.createElement('button');
    runBtn.className = 'test-center-btn test-center-btn-primary module-run-btn';
    runBtn.id = (isInteractive ? 'imodbtn-' : 'modbtn-') + safeId(mod.id);
    runBtn.textContent = '\u25b6 \u4e00\u952e\u6d4b\u8bd5';
    if (isInteractive) {
      runBtn.addEventListener('click', function() { runInteractiveModule(mod.id, runBtn); });
    } else {
      runBtn.addEventListener('click', function() { runModule(mod.id, runBtn); });
    }
    header.appendChild(runBtn);

    section.appendChild(header);

    var body = document.createElement('div');
    body.className = 'module-body';
    body.id = (isInteractive ? 'imodbody-' : 'modbody-') + safeId(mod.id);

    mod.tests.forEach(function(test) {
      var row = isInteractive ? createInteractiveTestRow(test, mod) : createTestRow(test, mod.id);
      body.appendChild(row);
    });

    section.appendChild(body);
    return section;
  }

  function renderInteractiveModules() {
    var container = document.getElementById('interactiveModuleList');
    container.innerHTML = '';

    interactiveModules.forEach(function(mod) {
      var section = createModuleSection(mod, true);
      container.appendChild(section);
    });
  }

  function getModuleIcon(id) {
    var icons = {
      'integration': '\ud83d\udd2c',
      'unit/agents': '\ud83e\uddd9',
      'unit/api': '\ud83c\udf10',
      'unit/data': '\ud83d\udcc4',
      'unit/llm': '\ud83e\udde0',
      'unit/memory': '\ud83d\udcda',
      'unit/models': '\ud83d\udce6',
      'unit/services': '\u26a1',
      'unit/session': '\ud83d\udcbe',
      'unit/systems': '\u2699\ufe0f',
    };
    return icons[id] || '\ud83d\udcc1';
  }

  function toggleModule(moduleId, btn, isInteractive) {
    var prefix = isInteractive ? 'imodbody-' : 'modbody-';
    var body = document.getElementById(prefix + safeId(moduleId));
    if (!body) return;
    var expanded = body.classList.toggle('expanded');
    btn.textContent = expanded ? '\u25bc' : '\u25b6';
  }

  function createTestRow(test, moduleId) {
    var row = document.createElement('div');
    row.className = 'test-row';
    row.id = 'row-' + safeId(test.name);

    var leftDiv = document.createElement('div');
    leftDiv.className = 'test-row-left';

    var nameSpan = document.createElement('span');
    nameSpan.className = 'test-row-name';
    nameSpan.textContent = test.name.split('/').pop().replace('.py', '').replace('test_', '');
    leftDiv.appendChild(nameSpan);

    var descSpan = document.createElement('span');
    descSpan.className = 'test-row-desc';
    descSpan.textContent = test.description;
    leftDiv.appendChild(descSpan);

    row.appendChild(leftDiv);

    var rightDiv = document.createElement('div');
    rightDiv.className = 'test-row-right';

    var statusBadge = document.createElement('span');
    statusBadge.className = 'test-row-status';
    statusBadge.id = 'rowstatus-' + safeId(test.name);
    statusBadge.textContent = '\u23f3';
    rightDiv.appendChild(statusBadge);

    var runBtn = document.createElement('button');
    runBtn.className = 'test-center-btn test-center-btn-sm';
    runBtn.id = 'rowbtn-' + safeId(test.name);
    runBtn.textContent = '\u25b6';
    runBtn.addEventListener('click', function() { runSingleTest(test.name, runBtn); });
    rightDiv.appendChild(runBtn);

    row.appendChild(rightDiv);

    var outputSection = document.createElement('div');
    outputSection.className = 'test-row-output';
    outputSection.id = 'rowout-' + safeId(test.name);
    outputSection.setAttribute('data-test-name', test.name);

    var resultBox = document.createElement('pre');
    resultBox.className = 'output-box';
    resultBox.id = 'rowresult-' + safeId(test.name);
    outputSection.appendChild(resultBox);

    row.appendChild(outputSection);

    return row;
  }

  function createInteractiveTestRow(test, mod) {
    var row = document.createElement('div');
    row.className = 'test-row interactive-test-row';
    row.id = 'irow-' + safeId(test.name);

    var leftDiv = document.createElement('div');
    leftDiv.className = 'test-row-left';

    var nameSpan = document.createElement('span');
    nameSpan.className = 'test-row-name';
    nameSpan.textContent = test.name.split('/').pop().replace('.py', '').replace('test_', '');
    leftDiv.appendChild(nameSpan);

    var descSpan = document.createElement('span');
    descSpan.className = 'test-row-desc';
    descSpan.textContent = test.description;
    leftDiv.appendChild(descSpan);

    row.appendChild(leftDiv);

    var rightDiv = document.createElement('div');
    rightDiv.className = 'test-row-right';

    var statusBadge = document.createElement('span');
    statusBadge.className = 'test-row-status';
    statusBadge.id = 'irowstatus-' + safeId(test.name);
    statusBadge.textContent = '\u23f3';
    rightDiv.appendChild(statusBadge);

    var runBtn = document.createElement('button');
    runBtn.className = 'test-center-btn test-center-btn-sm';
    runBtn.id = 'irowbtn-' + safeId(test.name);
    runBtn.textContent = '\u25b6';
    runBtn.addEventListener('click', function() { runInteractiveSingleTest(test.name, runBtn); });
    rightDiv.appendChild(runBtn);

    row.appendChild(rightDiv);

    var outputSection = document.createElement('div');
    outputSection.className = 'test-row-output';
    outputSection.id = 'irowout-' + safeId(test.name);
    outputSection.setAttribute('data-test-name', test.name);

    var resultBox = document.createElement('pre');
    resultBox.className = 'output-box';
    resultBox.id = 'irowresult-' + safeId(test.name);
    outputSection.appendChild(resultBox);

    row.appendChild(outputSection);

    return row;
  }

  async function runSingleTest(testName, btn) {
    btn.disabled = true;
    btn.textContent = '\u23f3';

    var sid = safeId(testName);
    var statusEl = document.getElementById('rowstatus-' + sid);
    var outputEl = document.getElementById('rowout-' + sid);
    var resultEl = document.getElementById('rowresult-' + sid);

    statusEl.className = 'test-row-status status-running';
    statusEl.textContent = '\u23f3 \u8fd0\u884c\u4e2d';
    outputEl.classList.add('show');
    resultEl.textContent = '\u6b63\u5728\u6267\u884c...';

    stats.running++;
    updateStats();

    try {
      var resp = await fetch(apiBase() + '/tests/run/' + testName, { method: 'POST' });
      var data = await resp.json();
      var elapsed = data.elapsed ? data.elapsed.toFixed(1) : '?';

      testResults[testName] = data;

      if (data.success) {
        statusEl.className = 'test-row-status status-success';
        statusEl.textContent = '\u2705 ' + elapsed + 's';
        stats.success++;
      } else {
        statusEl.className = 'test-row-status status-error';
        statusEl.textContent = '\u274c ' + elapsed + 's';
        stats.error++;
      }

      resultEl.textContent = formatOutput(testName, data, elapsed);

    } catch (err) {
      statusEl.className = 'test-row-status status-error';
      statusEl.textContent = '\u274c \u9519\u8bef';
      resultEl.textContent = '\u8bf7\u6c42\u5931\u8d25: ' + err.message;
      stats.error++;
    }

    stats.running--;
    updateStats();

    btn.disabled = false;
    btn.textContent = '\u25b6';

    updateModuleBadge(testName);
  }

  async function runModule(moduleId, btn, fromRunAll) {
    if (!fromRunAll) {
      btn.disabled = true;
      btn.textContent = '\u23f3 \u8fd0\u884c\u4e2d...';
    }

    var sid = safeId(moduleId);
    var badge = document.getElementById('badge-' + sid);
    badge.className = 'module-badge badge-running';
    badge.textContent = '\u23f3 \u8fd0\u884c\u4e2d...';

    var body = document.getElementById('modbody-' + sid);
    if (body && !body.classList.contains('expanded')) {
      body.classList.add('expanded');
      var expandBtn = body.parentElement.querySelector('.expand-btn');
      if (expandBtn) expandBtn.textContent = '\u25bc';
    }

    var mod = modules.find(function(m) { return m.id === moduleId; });
    if (!mod) {
      badge.className = 'module-badge badge-error';
      badge.textContent = '\u274c \u6a21\u5757\u672a\u627e\u5230';
      if (!fromRunAll) { btn.disabled = false; btn.textContent = '\u25b6 \u4e00\u952e\u6d4b\u8bd5'; }
      return;
    }

    var startTime = Date.now();
    var modPassed = 0, modFailed = 0, modSkipped = 0;

    for (var i = 0; i < mod.tests.length; i++) {
      var t = mod.tests[i];
      var tsid = safeId(t.name);
      var statusEl = document.getElementById('rowstatus-' + tsid);
      var resultEl = document.getElementById('rowresult-' + tsid);
      var outputEl = document.getElementById('rowout-' + tsid);

      if (statusEl) {
        statusEl.className = 'test-row-status status-running';
        statusEl.textContent = '\u23f3 \u8fd0\u884c\u4e2d';
      }
      if (resultEl) resultEl.textContent = '\u23f3 \u6b63\u5728\u6267\u884c...';
      if (outputEl) outputEl.classList.add('show');

      badge.textContent = '\u23f3 ' + (i + 1) + '/' + mod.tests.length + ' \u8fd0\u884c\u4e2d';

      try {
        var resp = await fetch(apiBase() + '/tests/run/' + t.name, { method: 'POST' });
        var r = await resp.json();
        var rElapsed = r.elapsed ? r.elapsed.toFixed(1) : '?';

        testResults[t.name] = r;

        if (r.success) {
          modPassed += r.cases_passed || 0;
          modFailed += r.cases_failed || 0;
          modSkipped += r.cases_skipped || 0;
        } else {
          modFailed += r.cases_failed || 0;
          modPassed += r.cases_passed || 0;
          modSkipped += r.cases_skipped || 0;
        }

        if (statusEl) {
          if (r.success) {
            statusEl.className = 'test-row-status status-success';
            statusEl.textContent = '\u2705 ' + rElapsed + 's';
            stats.success++;
          } else {
            statusEl.className = 'test-row-status status-error';
            statusEl.textContent = '\u274c ' + rElapsed + 's';
            stats.error++;
          }
        }

        if (resultEl) {
          resultEl.textContent = formatOutput(t.name, r, rElapsed);
        }
        if (outputEl && (verbose || !r.success || (resultEl && resultEl.textContent.indexOf('\n') > 0))) {
          outputEl.classList.add('show');
        }

      } catch (err) {
        if (statusEl) {
          statusEl.className = 'test-row-status status-error';
          statusEl.textContent = '\u274c \u9519\u8bef';
        }
        if (resultEl) resultEl.textContent = '\u8bf7\u6c42\u5931\u8d25: ' + err.message;
        stats.error++;
      }

      updateStats();
    }

    var elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    var modTotal = modPassed + modFailed + modSkipped;
    var badgeText = modTotal + '\u603b ' + modPassed + '\u901a\u8fc7';
    if (modFailed > 0) badgeText += ' ' + modFailed + '\u5931\u8d25';
    if (modSkipped > 0) badgeText += ' ' + modSkipped + '\u8df3\u8fc7';
    badgeText += ' (' + elapsed + 's)';

    if (modFailed === 0) {
      badge.className = 'module-badge badge-success';
      badge.textContent = '\u2705 ' + badgeText;
    } else {
      badge.className = 'module-badge badge-error';
      badge.textContent = '\u274c ' + badgeText;
    }

    if (!fromRunAll) {
      btn.disabled = false;
      btn.textContent = '\u25b6 \u4e00\u952e\u6d4b\u8bd5';
    }
  }

  async function runAll() {
    var btn = document.getElementById('runAllBtn');
    btn.disabled = true;
    btn.textContent = '\u23f3 \u6d4b\u8bd5\u4e2d...';

    stats.success = 0;
    stats.error = 0;
    stats.running = 0;
    updateStats();

    for (var i = 0; i < modules.length; i++) {
      var mod = modules[i];
      var modBtn = document.getElementById('modbtn-' + safeId(mod.id));
      btn.textContent = '\u23f3 ' + (i + 1) + '/' + modules.length + ' \u6a21\u5757';
      await runModule(mod.id, modBtn, true);
    }

    btn.disabled = false;
    btn.textContent = '\u25b6 \u5168\u90e8\u6d4b\u8bd5';
  }

  async function runInteractiveSingleTest(testName, btn) {
    btn.disabled = true;
    btn.textContent = '\u23f3';

    var sid = safeId(testName);
    var statusEl = document.getElementById('irowstatus-' + sid);
    var outputEl = document.getElementById('irowout-' + sid);
    var resultEl = document.getElementById('irowresult-' + sid);

    statusEl.className = 'test-row-status status-running';
    statusEl.textContent = '\u23f3 \u8c03\u7528LLM...';
    outputEl.classList.add('show');
    resultEl.textContent = '\u23f3 \u6b63\u5728\u4e0eNPC\u5bf9\u8bdd...\n';

    var dialogueLines = [];

    try {
      var resp = await fetch(apiBase() + '/tests/interactive/stream/' + testName);
      if (!resp.ok) {
        statusEl.className = 'test-row-status status-error';
        statusEl.textContent = '\u274c \u670d\u52a1\u7aef\u9519\u8bef ' + resp.status;
        resultEl.textContent = '\u8bf7\u6c42\u5931\u8d25: HTTP ' + resp.status;
        interactiveStats.failed++;
        updateInteractiveStats();
        btn.disabled = false;
        btn.textContent = '\u25b6';
        return;
      }
      if (!resp.body) {
        statusEl.className = 'test-row-status status-error';
        statusEl.textContent = '\u274c \u65e0\u54cd\u5e94\u4f53';
        resultEl.textContent = '\u8bf7\u6c42\u5931\u8d25: \u65e0\u54cd\u5e94\u4f53';
        interactiveStats.failed++;
        updateInteractiveStats();
        btn.disabled = false;
        btn.textContent = '\u25b6';
        return;
      }
      var reader = resp.body.getReader();
      var decoder = new TextDecoder();
      var buffer = '';

      while (true) {
        var chunk = await reader.read();
        if (chunk.done) break;
        buffer += decoder.decode(chunk.value, { stream: true });

        var lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (var i = 0; i < lines.length; i++) {
          var line = lines[i].trim();
          if (line.indexOf('data: ') !== 0) continue;
          var jsonStr = line.substring(6);
          try {
            var data = JSON.parse(jsonStr);
          } catch (e) { continue; }

          if (data.__error__) {
            resultEl.textContent += '\n\u274c ' + data.__error__;
            continue;
          }

          if (data.test_name !== undefined && data.success !== undefined) {
            var elapsed = data.elapsed ? data.elapsed.toFixed(1) : '?';
            interactiveResults[testName] = data;

            if (data.success) {
              statusEl.className = 'test-row-status status-success';
              statusEl.textContent = '\u2705 ' + elapsed + 's';
              interactiveStats.success++;
            } else {
              statusEl.className = 'test-row-status status-error';
              statusEl.textContent = '\u274c ' + elapsed + 's';
              interactiveStats.failed++;
            }

            var fullText = '';
            if (dialogueLines.length > 0) {
              fullText += '\u2501\u2501\u2501 \u5bf9\u8bdd\u8bb0\u5f55 \u2501\u2501\u2501\n' + dialogueLines.join('\n') + '\n\n';
            }
            fullText += '\u2501\u2501\u2501 \u6d4b\u8bd5\u7ed3\u679c \u2501\u2501\u2501\n';
            fullText += data.output || (data.success ? '\u2705 \u901a\u8fc7' : '\u274c \u5931\u8d25');
            resultEl.textContent = fullText;
            updateInteractiveStats();
            continue;
          }

          if (data.npc || data.player) {
            var npcName = data.npc_name || data.npc || '?';
            var playerMsg = data.player || '';
            var reply = data.reply || '';
            var fav = data.favor_delta || 0;
            var coin = data.coin_delta || 0;

            var lineText = '\n\u3010' + npcName + '\u3011\u4f60\uff1a' + playerMsg;
            resultEl.textContent += lineText + '\n';
            dialogueLines.push(lineText);

            statusEl.textContent = '\u23f3 ' + npcName + '\u56de\u590d\u4e2d...';

            await new Promise(function(resolve) { setTimeout(resolve, 50); });

            var replyText = '\u3010' + npcName + '\u3011' + reply;
            resultEl.textContent += replyText + '\n';
            dialogueLines.push(replyText);

            if (fav !== 0 || coin !== 0) {
              var changes = [];
              if (fav !== 0) changes.push('\u597d\u611f' + (fav > 0 ? '+' : '') + fav);
              if (coin !== 0) changes.push('\u91d1\u94b1' + (coin > 0 ? '+' : '') + coin);
              var changeText = '  \u2192 ' + changes.join(', ');
              resultEl.textContent += changeText + '\n';
              dialogueLines.push(changeText);
            }

            resultEl.scrollTop = resultEl.scrollHeight;
          }
        }
      }

    } catch (err) {
      statusEl.className = 'test-row-status status-error';
      statusEl.textContent = '\u274c \u9519\u8bef';
      resultEl.textContent += '\n\u8bf7\u6c42\u5931\u8d25: ' + err.message;
      interactiveStats.failed++;
      updateInteractiveStats();
    }

    btn.disabled = false;
    btn.textContent = '\u25b6';
  }

  async function runInteractiveModule(moduleId, btn, fromRunAll) {
    if (!fromRunAll) {
      btn.disabled = true;
      btn.textContent = '\u23f3 \u8fd0\u884c\u4e2d...';
    }

    var sid = safeId(moduleId);
    var badge = document.getElementById('ibadge-' + sid);
    badge.className = 'module-badge badge-running';
    badge.textContent = '\u23f3 \u8c03\u7528LLM...';

    var body = document.getElementById('imodbody-' + sid);
    if (body && !body.classList.contains('expanded')) {
      body.classList.add('expanded');
      var expandBtn = body.parentElement.querySelector('.expand-btn');
      if (expandBtn) expandBtn.textContent = '\u25bc';
    }

    var mod = interactiveModules.find(function(m) { return m.id === moduleId; });
    if (!mod) {
      badge.className = 'module-badge badge-error';
      badge.textContent = '\u274c \u6a21\u5757\u672a\u627e\u5230';
      if (!fromRunAll) { btn.disabled = false; btn.textContent = '\u25b6 \u4e00\u952e\u6d4b\u8bd5'; }
      return;
    }

    var startTime = Date.now();
    var modPassed = 0, modFailed = 0;

    for (var i = 0; i < mod.tests.length; i++) {
      var t = mod.tests[i];
      badge.textContent = '\u23f3 ' + modPassed + '\u2705 ' + modFailed + '\u274c ' + (i + 1) + '/' + mod.tests.length + ' \u8fd0\u884c\u4e2d';

      var tBtn = document.getElementById('irowbtn-' + safeId(t.name));
      if (tBtn) {
        await runInteractiveSingleTest(t.name, tBtn);
      }

      if (interactiveResults[t.name]) {
        if (interactiveResults[t.name].success) {
          modPassed++;
        } else {
          modFailed++;
        }
      }

      badge.textContent = '\u23f3 ' + modPassed + '\u2705 ' + modFailed + '\u274c ' + (i + 1) + '/' + mod.tests.length;
    }

    var elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    var modTotal = modPassed + modFailed;
    var badgeText = modTotal + '\u603b ' + modPassed + '\u901a\u8fc7';
    if (modFailed > 0) badgeText += ' ' + modFailed + '\u5931\u8d25';
    badgeText += ' (' + elapsed + 's)';

    if (modFailed === 0) {
      badge.className = 'module-badge badge-success';
      badge.textContent = '\u2705 ' + badgeText;
    } else {
      badge.className = 'module-badge badge-error';
      badge.textContent = '\u274c ' + badgeText;
    }

    if (!fromRunAll) {
      btn.disabled = false;
      btn.textContent = '\u25b6 \u4e00\u952e\u6d4b\u8bd5';
    }
  }

  async function runInteractiveAll() {
    var btn = document.getElementById('interactiveRunAllBtn');
    btn.disabled = true;
    btn.textContent = '\u23f3 \u6d4b\u8bd5\u4e2d...';

    interactiveStats.success = 0;
    interactiveStats.failed = 0;
    interactiveResults = {};
    updateInteractiveStats();

    for (var i = 0; i < interactiveModules.length; i++) {
      var mod = interactiveModules[i];
      var modBtn = document.getElementById('imodbtn-' + safeId(mod.id));
      btn.textContent = '\u23f3 ' + (i + 1) + '/' + interactiveModules.length + ' \u6a21\u5757';
      await runInteractiveModule(mod.id, modBtn, true);
    }

    btn.disabled = false;
    btn.textContent = '\u25b6 \u5168\u90e8\u4ea4\u4e92\u6d4b\u8bd5';
  }

  function formatOutput(testName, data, elapsed) {
    var output = data.output || '';
    if (verbose) {
      return '[' + testName + '] \u8017\u65f6: ' + elapsed + 's [\u9000\u51fa\u7801: ' + (data.exit_code ?? '?') + ']\n\n' + output;
    }
    if (data.success) {
      var summary = extractSummary(output);
      if (summary) {
        return '\u2705 \u901a\u8fc7 (' + elapsed + 's)\n' + summary;
      }
      return '\u2705 \u901a\u8fc7 (' + elapsed + 's)';
    }
    var failInfo = extractFailure(output);
    if (failInfo) {
      return '\u274c \u5931\u8d25: ' + failInfo;
    }
    var lines = output.trim().split('\n');
    var lastErr = '';
    for (var i = lines.length - 1; i >= 0; i--) {
      if (lines[i].trim()) {
        lastErr = lines[i].trim();
        break;
      }
    }
    return '\u274c \u5931\u8d25: ' + lastErr;
  }

  function formatInteractiveOutput(data, elapsed) {
    var dialogueLog = data.dialogue_log || [];
    var dialogueHtml = '';

    if (dialogueLog.length > 0) {
      dialogueHtml += '\n\u2501\u2501\u2501 \u5bf9\u8bdd\u8bb0\u5f55 \u2501\u2501\u2501\n';
      for (var i = 0; i < dialogueLog.length; i++) {
        var entry = dialogueLog[i];
        var npcName = entry.npc_name || entry.npc || '?';
        var playerMsg = entry.player || '';
        var reply = entry.reply || '';
        var fav = entry.favor_delta || 0;
        var coin = entry.coin_delta || 0;

        dialogueHtml += '\n\u3010' + npcName + '\u3011\u4f60\uff1a' + playerMsg + '\n';
        dialogueHtml += '\u3010' + npcName + '\u3011' + reply + '\n';
        if (fav !== 0 || coin !== 0) {
          var changes = [];
          if (fav !== 0) changes.push('\u597d\u611f' + (fav > 0 ? '+' : '') + fav);
          if (coin !== 0) changes.push('\u91d1\u94b1' + (coin > 0 ? '+' : '') + coin);
          dialogueHtml += '  \u2192 ' + changes.join(', ') + '\n';
        }
      }
      dialogueHtml += '\n';
    }

    if (interactiveVerbose) {
      return (data.success ? '\u2705' : '\u274c') + ' ' + (data.test_name || '') + ' (' + elapsed + 's)\n' + dialogueHtml + data.output;
    }

    if (data.success) {
      if (dialogueHtml) {
        return '\u2705 \u901a\u8fc7 (' + elapsed + 's)\n' + dialogueHtml;
      }
      return '\u2705 \u901a\u8fc7 (' + elapsed + 's)';
    }

    var output = data.output || '';
    var firstFail = '';
    var lines = output.trim().split('\n');
    for (var i = 0; i < lines.length; i++) {
      if (lines[i].indexOf('FAIL:') >= 0 || lines[i].indexOf('ERROR:') >= 0) {
        firstFail = lines[i].trim();
        break;
      }
    }
    if (firstFail) {
      return '\u274c ' + firstFail + '\n' + dialogueHtml;
    }
    return '\u274c \u5931\u8d25 (' + elapsed + 's)\n' + dialogueHtml + output.substring(0, 200);
  }

  function extractSummary(output) {
    if (!output) return '';
    var lines = output.trim().split('\n');
    for (var i = lines.length - 1; i >= 0; i--) {
      var line = lines[i].trim();
      if (line.indexOf('passed') >= 0 || line.indexOf('PASSED') >= 0) {
        return line;
      }
    }
    return '';
  }

  function extractFailure(output) {
    if (!output) return '';
    var lines = output.trim().split('\n');
    var failLine = '';
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i].trim();
      if (line.indexOf('FAILED') >= 0) {
        failLine = line;
      }
    }
    if (failLine) return failLine;
    for (var i = lines.length - 1; i >= 0; i--) {
      var line = lines[i].trim();
      if (line && line.indexOf('=') < 0 && line.indexOf('-') !== 0) {
        return line;
      }
    }
    return '';
  }

  function updateModuleBadge(testName) {
    for (var i = 0; i < modules.length; i++) {
      var mod = modules[i];
      for (var j = 0; j < mod.tests.length; j++) {
        if (mod.tests[j].name === testName) {
          recalcModuleBadge(mod);
          return;
        }
      }
    }
  }

  function recalcModuleBadge(mod) {
    var sid = safeId(mod.id);
    var badge = document.getElementById('badge-' + sid);
    if (!badge) return;

    var tested = 0, passed = 0, failed = 0, skipped = 0;
    mod.tests.forEach(function(t) {
      if (testResults[t.name]) {
        tested++;
        if (testResults[t.name].success) {
          passed++;
        } else {
          failed++;
        }
        skipped += testResults[t.name].cases_skipped || 0;
      }
    });

    if (tested === 0) {
      badge.className = 'module-badge';
      badge.textContent = '\u23f3 \u5f85\u6d4b';
    } else if (tested < mod.count) {
      badge.className = 'module-badge badge-running';
      badge.textContent = '\u23f3 ' + passed + '/' + tested + ' \u5df2\u6d4b';
    } else if (failed === 0) {
      badge.className = 'module-badge badge-success';
      var text = tested + '\u603b ' + passed + '\u901a\u8fc7';
      if (skipped > 0) text += ' ' + skipped + '\u8df3\u8fc7';
      badge.textContent = '\u2705 ' + text;
    } else {
      badge.className = 'module-badge badge-error';
      var text = tested + '\u603b ' + passed + '\u901a\u8fc7 ' + failed + '\u5931\u8d25';
      if (skipped > 0) text += ' ' + skipped + '\u8df3\u8fc7';
      badge.textContent = '\u274c ' + text;
    }
  }

  function toggleVerbose() {
    verbose = document.getElementById('verboseToggle').checked;

    document.querySelectorAll('#functionalPanel .test-row-output').forEach(function(el) {
      var testName = el.getAttribute('data-test-name');
      var resultEl = el.querySelector('.output-box');

      if (!verbose) {
        if (testResults[testName] && testResults[testName].success) {
          el.classList.remove('show');
        }
      } else {
        if (testResults[testName]) {
          el.classList.add('show');
        }
      }

      if (resultEl && testResults[testName]) {
        var r = testResults[testName];
        var e = r.elapsed ? r.elapsed.toFixed(1) : '?';
        resultEl.textContent = formatOutput(testName, r, e);
      }
    });
  }

  function toggleInteractiveVerbose() {
    interactiveVerbose = document.getElementById('interactiveVerboseToggle').checked;

    document.querySelectorAll('#interactivePanel .test-row-output').forEach(function(el) {
      var testName = el.getAttribute('data-test-name');
      var resultEl = el.querySelector('.output-box');

      if (!interactiveVerbose) {
        if (interactiveResults[testName] && interactiveResults[testName].success) {
          el.classList.remove('show');
        }
      } else {
        if (interactiveResults[testName]) {
          el.classList.add('show');
        }
      }

      if (resultEl && interactiveResults[testName]) {
        var r = interactiveResults[testName];
        var e = r.elapsed ? r.elapsed.toFixed(1) : '?';
        resultEl.textContent = formatInteractiveOutput(r, e);
      }
    });
  }

  function updateStats() {
    var runningEl = document.getElementById('runningCount');
    if (runningEl) runningEl.textContent = stats.running;
    var successEl = document.getElementById('successCount');
    if (successEl) successEl.textContent = stats.success;
    var errorEl = document.getElementById('errorCount');
    if (errorEl) errorEl.textContent = stats.error;
  }

  function updateInteractiveStats() {
    var successEl = document.getElementById('interactiveSuccess');
    if (successEl) successEl.textContent = interactiveStats.success;
    var failedEl = document.getElementById('interactiveFailed');
    if (failedEl) failedEl.textContent = interactiveStats.failed;
  }

  window.TestCenter = {
    runAll: runAll,
    toggleVerbose: toggleVerbose,
    switchTab: switchTab,
    runInteractiveAll: runInteractiveAll,
    runInteractiveModule: runInteractiveModule,
    toggleInteractiveVerbose: toggleInteractiveVerbose,
  };

  document.addEventListener('DOMContentLoaded', loadModules);

})(window.App);
