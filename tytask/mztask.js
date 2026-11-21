/*!
 * mztask.js — 任务进度模型（独立可复用）
 * 零依赖，UMD：script 标签 / CommonJS 都能用。
 *
 * 用法（三步）：
 *   1. 页面上放一个空容器：<div id="tasks"></div>
 *   2. 引入本文件（script src="mztask.js"）
 *   3. 调用 MZTask.mount('#tasks', { title: '任务', storageKey: 'myapp.tasks' })
 *
 * 能力：增删改、三态流转、完成时记「问题原因 + 解决方案」、历史进度、
 *       生成 agent prompt（模板可改）、JSON 导入导出、存储可替换。
 * 版本：1.2.0
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.MZTask = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var VERSION = '1.2.0';

  var DEFAULT_RULE = [
    '执行规则（重要）：',
    '1. 先复述你的实施计划（分步骤）；',
    '2. 说明风险点：会动到哪些文件/功能，数据会不会受影响；',
    '3. 提 1-3 条你认为更好的改进建议；',
    '4. 等我确认后再动手，不要直接改代码。'
  ].join('\n');

  var DEFAULT_TPL = [
    '你是这个项目的开发 agent。下面是当前要做的事，请按规则处理。',
    '',
    '{rules}',
    '',
    '当前任务清单（共 {count} 条）：',
    '{tasks}',
    '',
    '完成一条就把它的状态改成已解决，并把新的问题/需求继续记在任务板里。'
  ].join('\n');

  var GROUP = { doing: '进行中', todo: '待办', done: '已解决' };
  var FLAG = { doing: '进行中', todo: '待办', done: '✓ 已完成' };
  var ORDER = ['doing', 'todo', 'done'];

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c];
    });
  }
  function now() { return Date.now(); }
  function fmt(ts) {
    var d = new Date(ts), p = function (n) { return (n < 10 ? '0' : '') + n; };
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
  }
  function dayKey(ts) {
    var d = new Date(ts || Date.now());
    return d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2);
  }

  var CSS = [
    '.mzt{--mzt-bg:#151d33;--mzt-line:#26304f;--mzt-text:#e6ecff;--mzt-dim:#8b96b8;--mzt-gold:#e8c37a;--mzt-accent:#6f8ff5;',
    'font-size:13px;color:var(--mzt-text);font-family:"Microsoft YaHei",system-ui,sans-serif;',
    'width:100%;max-width:960px;margin:0 auto;padding:4px}',
    '.mzt *{box-sizing:border-box}',
    '.mzt .mzt-bar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:10px}',
    '.mzt .mzt-stat{color:var(--mzt-dim);font-size:11.5px}',
    '.mzt .mzt-in{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px}',
    '.mzt input[type=text],.mzt textarea,.mzt select{background:#0f1320;border:1px solid var(--mzt-line);border-radius:8px;',
    'color:var(--mzt-text);padding:7px 9px;font-size:12.5px;font-family:inherit;outline:none}',
    '.mzt input[type=text]:focus,.mzt textarea:focus{border-color:var(--mzt-accent)}',
    '.mzt .mzt-title{flex:1;min-width:180px}',
    '.mzt .mzt-detail{width:100%;min-height:52px;resize:vertical;line-height:1.6}',
    '.mzt button{cursor:pointer;font-family:inherit;font-size:12px;border-radius:8px;padding:6px 12px;',
    'border:1px solid var(--mzt-line);background:#1b2440;color:var(--mzt-text);transition:.13s}',
    '.mzt button:hover{border-color:var(--mzt-accent)}',
    '.mzt button.pri{background:linear-gradient(180deg,#3a6f5a,#2b5a48);border-color:#4f9d7a;color:#fff;font-weight:600}',
    '.mzt .mzt-sec{margin-top:12px}',
    '.mzt .mzt-sec-h{font-size:12px;color:var(--mzt-gold);font-weight:700;margin:10px 0 6px}',
    '.mzt .mzt-list{display:flex;flex-direction:column;gap:7px}',
    '.mzt .mzt-row{display:flex;align-items:flex-start;gap:9px;padding:9px 11px;border:1px solid var(--mzt-line);',
    'border-radius:10px;background:rgba(255,255,255,.015)}',
    '.mzt .mzt-row.done{border-color:#2c4a3d;background:rgba(79,157,122,.06)}',
    '.mzt .mzt-row .flag{flex:0 0 auto;font-size:10.5px;padding:2px 7px;border-radius:20px;',
    'background:#232b47;color:#9fb4ff;white-space:nowrap}',
    '.mzt .mzt-row.done .flag{background:rgba(79,209,165,.14);color:#4fd1a5}',
    '.mzt .mzt-row .body{flex:1;min-width:0}',
    '.mzt .mzt-row .t{font-weight:600;font-size:13px;color:#fff}',
    '.mzt .mzt-row.done .t{color:#8fd8b3;text-decoration:line-through}',
    '.mzt .mzt-row .d{color:var(--mzt-dim);font-size:12px;white-space:pre-wrap;margin-top:3px;line-height:1.65}',
    '.mzt .mzt-row .fx{margin-top:6px;font-size:12px;line-height:1.7;white-space:pre-wrap;',
    'color:#b9cbff;background:rgba(111,143,245,.08);border-left:2px solid #4f6fb8;border-radius:0 6px 6px 0;padding:6px 9px}',
    '.mzt .mzt-row .fx b{color:#8fa8ff}',
    '.mzt .mzt-row .fx.cause{color:#e6c98a;background:rgba(232,195,122,.07);border-left-color:#b8863a}',
    '.mzt .mzt-row .fx.cause b{color:#e8c37a}',
    '.mzt .mzt-row .fx.empty{color:#6f7a99;background:transparent;border-left-color:#2b3456;font-style:italic}',
    '.mzt .mzt-row .meta{color:#6f7a99;font-size:11px;margin-top:5px}',
    '.mzt .mzt-row .src{margin-top:4px;font-size:11px;color:#6f7a99;word-break:break-all}',
    '.mzt .mzt-row .src b{color:#8fa8ff;font-weight:400}',
    '.mzt button.mzt-ann.on{background:linear-gradient(180deg,#8a5a2b,#6d4620);border-color:#c08a4a;color:#fff;font-weight:600}',
    '.mzt-ann-hl{position:fixed;pointer-events:none;z-index:99998;border:2px solid #e8c37a;',
    'background:rgba(232,195,122,.12);border-radius:4px;display:none}',
    '.mzt-ann-hl.on{display:block}',
    '.mzt-annotating,.mzt-annotating *{cursor:crosshair!important}',
    '.mzt .mzt-row .ops{display:flex;gap:5px;flex-wrap:wrap;justify-content:flex-end;max-width:160px}',
    '.mzt .mzt-row .ops button{padding:4px 9px;font-size:11.5px}',
    '.mzt .mzt-empty{color:var(--mzt-dim);font-size:12px;padding:6px 2px}',
    '.mzt .mzt-hist-sum{color:var(--mzt-dim);font-size:12px;margin-bottom:6px}',
    '.mzt .mzt-hist-sum b{color:var(--mzt-gold)}',
    '.mzt .mzt-hday{display:flex;justify-content:space-between;font-size:11.5px;color:var(--mzt-dim);margin-top:8px}',
    '.mzt .mzt-hist-ul{margin:4px 0 0;padding-left:18px;font-size:12px;line-height:1.9;color:#c3cdea}',
    '.mzt .mzt-hist-ul .k{font-size:10.5px;color:#8b96b8;margin-left:6px}',
    '.mzt .mzt-prompt{width:100%;min-height:170px;line-height:1.65;white-space:pre-wrap;',
    'font-family:Consolas,"Microsoft YaHei",monospace;resize:vertical}',
    '.mzt details.mzt-tpl{margin-top:10px;border-top:1px dashed var(--mzt-line);padding-top:8px}',
    '.mzt details.mzt-tpl summary{cursor:pointer;color:var(--mzt-dim);font-size:12px;list-style:none}',
    '.mzt details.mzt-tpl summary::-webkit-details-marker{display:none}',
    '.mzt details.mzt-tpl summary:before{content:"▸ ";color:#6f7fa8}',
    '.mzt details.mzt-tpl[open] summary:before{content:"▾ "}',
    '.mzt .mzt-hint{font-size:11.5px;color:var(--mzt-dim);line-height:1.9;margin:7px 0 6px}',
    '.mzt .mzt-hint code{background:#0f1320;border:1px solid var(--mzt-line);border-radius:4px;padding:1px 5px;color:#9fb4ff;font-size:11px}',
    '.mzt-mask{position:fixed;inset:0;background:rgba(0,0,0,.55);display:none;align-items:center;justify-content:center;z-index:99999}',
    '.mzt-mask.on{display:flex}',
    '.mzt-box{width:min(560px,92vw);max-height:90vh;overflow:auto;background:var(--mzt-bg,#151d33);border:1px solid var(--mzt-line,#2b3456);',
    'border-radius:12px;padding:16px;box-shadow:0 18px 50px rgba(0,0,0,.5);font-family:"Microsoft YaHei",system-ui,sans-serif}',
    '.mzt-box .h{font-size:13px;color:var(--mzt-gold,#e8c37a);font-weight:700;margin-bottom:8px}',
    '.mzt-box .lbl{font-size:11.5px;color:#8b96b8;margin:8px 0 4px}',
    '.mzt-box textarea{width:100%;min-height:78px;background:#0f1320;border:1px solid var(--mzt-line,#2b3456);border-radius:8px;',
    'color:var(--mzt-text,#e6ecff);padding:9px;font-size:12.5px;font-family:inherit;line-height:1.7;resize:vertical;outline:none}',
    '.mzt-box textarea:focus{border-color:var(--mzt-accent,#6f8ff5)}',
    '.mzt-box .b{display:flex;gap:8px;justify-content:flex-end;margin-top:12px}',
    '.mzt-toast{position:fixed;left:50%;bottom:26px;transform:translateX(-50%) translateY(8px);background:#1b2440;',
    'border:1px solid #4f6fb8;color:#eaf0ff;padding:9px 16px;border-radius:10px;font-size:12.5px;z-index:100000;',
    'opacity:0;pointer-events:none;transition:opacity .16s,transform .16s;font-family:"Microsoft YaHei",system-ui,sans-serif}',
    '.mzt-toast.on{opacity:1;transform:translateX(-50%) translateY(0)}'
  ].join('');

  function injectCss() {
    if (document.getElementById('mztask-style')) return;
    var st = document.createElement('style');
    st.id = 'mztask-style';
    st.textContent = CSS;
    document.head.appendChild(st);
  }

  /* ---------- 存储适配器 ----------
     接口（全部返回 Promise）：
       name                  名字，调试用
       load()                -> { tasks, seq, promptTpl }
       save(state)           整体保存（localStorage / 宿主 postMessage 用这个）
       apply(op)?            可选，增量：op = { type:'put', task } | { type:'del', id }
                             有 apply 时 mount 只写变化的记录；没有就整体 save

     内置：local() / host() / memory()
     扩展：自己写一个满足上面接口的对象，mount({ adapter: 你的对象 })
     默认：检测到 window.chrome.webview → host，否则 local */
  /* IndexedDB 小工具（idb 适配器用） */
  function openIdb(name) {
    return new Promise(function (res, rej) {
      if (!window.indexedDB) return rej(new Error('no indexedDB'));
      var req = indexedDB.open(name, 1);
      req.onupgradeneeded = function () {
        var db = req.result;
        if (!db.objectStoreNames.contains('tasks')) db.createObjectStore('tasks', { keyPath: 'id' });
        if (!db.objectStoreNames.contains('handles')) db.createObjectStore('handles', { keyPath: 'k' });
      };
      req.onsuccess = function () { res(req.result); };
      req.onerror = function () { rej(req.error || new Error('idb open failed')); };
    });
  }
  function idbReq(r) {
    return new Promise(function (res, rej) {
      r.onsuccess = function () { res(r.result); };
      r.onerror = function () { rej(r.error); };
    });
  }
  function idbTx(db, names, mode, fn) {
    return new Promise(function (res, rej) {
      var t;
      try { t = db.transaction(names, mode); } catch (e) { return rej(e); }
      var out;
      try { out = fn(t); } catch (e) { return rej(e); }
      t.oncomplete = function () { res(out); };
      t.onerror = function () { rej(t.error); };
      t.onabort = function () { rej(t.error); };
    });
  }

  var adapters = {
    memory: function () {
      var state = { tasks: [], seq: 1 };
      return {
        name: 'memory',
        load: function () { return Promise.resolve(JSON.parse(JSON.stringify(state))); },
        save: function (x) { state = JSON.parse(JSON.stringify(x)); return Promise.resolve(); }
      };
    },

    local: function (opts) {
      var key = (opts && opts.storageKey) || 'mztask.v1';
      return {
        name: 'localStorage',
        load: function () {
          return Promise.resolve().then(function () {
            try {
              var d = JSON.parse(localStorage.getItem(key) || 'null');
              if (d && Array.isArray(d.tasks)) return d;
              /* 第一次打开：用 data.js 里 window.__MZTASK_DATA__ 当基线 */
              var seed = window.__MZTASK_DATA__;
              if (seed && Array.isArray(seed.tasks)) {
                try { localStorage.setItem(key, JSON.stringify(seed)); } catch (e) {}
                return { tasks: seed.tasks, seq: seed.seq || 1, promptTpl: seed.promptTpl };
              }
              return { tasks: [], seq: 1 };
            } catch (e) { return { tasks: [], seq: 1 }; }
          });
        },
        save: function (st) {
          return Promise.resolve().then(function () {
            try { localStorage.setItem(key, JSON.stringify(st)); } catch (e) {}
          });
        }
      };
    },

    host: function (opts) {
      var wv = window.chrome && window.chrome.webview;
      var loadUrl = (opts && opts.loadUrl) || '/board.json';
      var saveTag = (opts && opts.saveTag) || 'TBA|save|';
      return {
        name: 'host',
        load: function () {
          if (!wv) return Promise.resolve({ tasks: [], seq: 1 });
          return fetch(loadUrl, { cache: 'no-store' })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (d) {
              return d && Array.isArray(d.tasks)
                ? { tasks: d.tasks, seq: d.seq || 1, promptTpl: d.promptTpl }
                : { tasks: [], seq: 1 };
            })
            .catch(function () { return { tasks: [], seq: 1 }; });
        },
        save: function (st) {
          if (!wv) return Promise.resolve();
          try {
            wv.postMessage(saveTag + JSON.stringify({
              tasks: st.tasks || [], seq: st.seq || 1, notes: []
            }));
          } catch (e) {}
          return Promise.resolve();
        }
      };
    },

    /* IndexedDB：记录级，改只写一条 */
    idb: function (opts) {
      var dbName = (opts && opts.dbName) || ('mztask_' + ((opts && opts.storageKey) || 'default').replace(/[^\w]/g, '_'));
      var META = '__meta__';
      var dbp = null;
      function db() { if (!dbp) dbp = openIdb(dbName); return dbp; }
      return {
        name: 'idb',
        load: function () {
          return db().then(function (d) {
            return idbTx(d, ['tasks'], 'readonly', function (t) { return idbReq(t.objectStore('tasks').getAll()); })
              .then(function (all) {
                var meta = (all || []).filter(function (x) { return x.id === META; })[0] || {};
                return {
                  tasks: (all || []).filter(function (x) { return x.id !== META; }),
                  seq: meta.seq || 1, promptTpl: meta.promptTpl
                };
              });
          }).catch(function () { return { tasks: [], seq: 1 }; });
        },
        save: function (st) {
          return db().then(function (d) {
            return idbTx(d, ['tasks'], 'readwrite', function (t) {
              var os = t.objectStore('tasks');
              os.clear();
              (st.tasks || []).forEach(function (x) { os.put(x); });
              os.put({ id: META, seq: st.seq || 1, promptTpl: st.promptTpl });
            });
          }).catch(function () {});
        },
        apply: function (op) {
          return db().then(function (d) {
            return idbTx(d, ['tasks'], 'readwrite', function (t) {
              var os = t.objectStore('tasks');
              if (op.type === 'put') os.put(op.task); else os.delete(op.id);
            });
          }).catch(function () {});
        },
        saveMeta: function (m) {
          return db().then(function (d) {
            return idbTx(d, ['tasks'], 'readwrite', function (t) {
              t.objectStore('tasks').put({ id: META, seq: m.seq || 1, promptTpl: m.promptTpl });
            });
          }).catch(function () {});
        }
      };
    },

    /* OPFS：浏览器私有文件系统，一个任务一个文件 */
    opfs: function (opts) {
      var dirName = (opts && opts.dirName) || 'mztask';
      var META = '_meta.json';
      function dir() {
        if (!navigator.storage || !navigator.storage.getDirectory) {
          return Promise.reject(new Error('no opfs'));
        }
        return navigator.storage.getDirectory()
          .then(function (root) { return root.getDirectoryHandle(dirName, { create: true }); });
      }
      function readText(handle) {
        return handle.getFile().then(function (f) { return f.text(); });
      }
      function writeText(dh, name, text) {
        return dh.getFileHandle(name, { create: true }).then(function (fh) {
          return fh.createWritable().then(function (w) {
            return w.write(text).then(function () { return w.close(); });
          });
        });
      }
      function entries(dh) {
        var out = [];
        if (!dh || typeof dh.values !== 'function') return Promise.resolve(out);
        var it = dh.values();
        function step() {
          return it.next().then(function (r) {
            if (r.done) return out;
            out.push(r.value);
            return step();
          });
        }
        return step();
      }
      return {
        name: 'opfs',
        load: function () {
          return dir().then(function (dh) {
            return entries(dh).then(function (list) {
              var tasks = [], meta = {};
              var jobs = list.map(function (h) {
                if (h.kind !== 'file') return Promise.resolve();
                return readText(h).then(function (txt) {
                  try {
                    var o = JSON.parse(txt);
                    if (h.name === META) meta = o || {};
                    else if (o && o.id) tasks.push(o);
                  } catch (e) {}
                }).catch(function () {});
              });
              return Promise.all(jobs).then(function () {
                return { tasks: tasks, seq: meta.seq || 1, promptTpl: meta.promptTpl };
              });
            });
          }).catch(function () { return { tasks: [], seq: 1 }; });
        },
        save: function (st) {
          return dir().then(function (dh) {
            return entries(dh).then(function (list) {
              return Promise.all(list.map(function (h) {
                return dh.removeEntry(h.name).catch(function () {});
              })).then(function () {
                return Promise.all((st.tasks || []).map(function (t) {
                  return writeText(dh, t.id + '.json', JSON.stringify(t)).catch(function () {});
                })).then(function () {
                  return writeText(dh, META, JSON.stringify({ seq: st.seq || 1, promptTpl: st.promptTpl })).catch(function () {});
                });
              });
            });
          }).catch(function () {});
        },
        apply: function (op) {
          return dir().then(function (dh) {
            if (op.type === 'put') return writeText(dh, op.task.id + '.json', JSON.stringify(op.task));
            return dh.removeEntry(op.id + '.json').catch(function () {});
          }).catch(function () {});
        },
        saveMeta: function (m) {
          return dir().then(function (dh) {
            return writeText(dh, META, JSON.stringify({ seq: m.seq || 1, promptTpl: m.promptTpl }));
          }).catch(function () {});
        }
      };
    },

    /* 单文件（File System Access）：JSONL 追加日志 */
    /* data.js：数据就是一个 js 文件（window.__MZTASK_DATA__ = {...}），
       拿到文件句柄后每次改动直接覆盖写回，不用手动导出。 */
    jsfile: function (opts) {
      var handle = opts && opts.handle;
      if (!handle) throw new Error('adapters.jsfile 需要一个 handle（先用 MZTask.pickFile() 选/建 data.js）');
      return {
        name: 'jsfile',
        handle: handle,
        load: function () {
          return handle.getFile()
            .then(function (f) { return f.text(); })
            .then(function (txt) {
              var d = parseDataJs(txt);
              return d && Array.isArray(d.tasks)
                ? { tasks: d.tasks, seq: d.seq || 1, promptTpl: d.promptTpl }
                : { tasks: [], seq: 1 };
            })
            .catch(function () { return { tasks: [], seq: 1 }; });
        },
        save: function (st) {
          var text = buildDataJs(st);
          return handle.createWritable()
            .then(function (w) { return w.write(text).then(function () { return w.close(); }); })
            .catch(function () {});
        }
      };
    },

    file: function (opts) {
      var handle = opts && opts.handle;
      if (!handle) throw new Error('adapters.file 需要一个 handle（先用 MZTask.pickFile() 选文件）');
      var queue = Promise.resolve();
      function readText() {
        return handle.getFile().then(function (f) { return f.text(); });
      }
      function append(ops) {
        if (!ops || !ops.length) return Promise.resolve();
        var text = ops.map(function (o) { return JSON.stringify(o); }).join('\n') + '\n';
        queue = queue.then(function () {
          return handle.getFile().then(function (f) {
            return handle.createWritable({ keepExistingData: true }).then(function (w) {
              return w.seek(f.size).then(function () { return w.write(text); }).then(function () { return w.close(); });
            });
          });
        }).catch(function () {});
        return queue;
      }
      return {
        name: 'file',
        load: function () {
          return readText().then(function (txt) { return replay(txt); })
            .catch(function () { return { tasks: [], seq: 1 }; });
        },
        save: function (st) {
          var text = (st.tasks || []).map(function (t) {
            return JSON.stringify({ t: 'add', at: Date.now(), task: t });
          }).join('\n') + ((st.tasks || []).length ? '\n' : '');
          return handle.createWritable().then(function (w) {
            return w.write(text).then(function () { return w.close(); });
          }).catch(function () {});
        },
        apply: function (op) {
          return append([op.type === 'put'
            ? { t: 'upsert', at: Date.now(), task: op.task }
            : { t: 'delete', at: Date.now(), id: op.id }]);
        }
      };
    },

    /* 目录（File System Access）：一个任务一个文件 */
    dir: function (opts) {
      var handle = opts && opts.handle;
      if (!handle) throw new Error('adapters.dir 需要一个目录 handle（先用 MZTask.pickDir() 选目录）');
      var META = '_meta.json';
      function entries() {
        var out = [];
        if (typeof handle.values !== 'function') return Promise.resolve(out);
        var it = handle.values();
        function step() {
          return it.next().then(function (r) {
            if (r.done) return out;
            out.push(r.value);
            return step();
          });
        }
        return step();
      }
      function readText(h) { return h.getFile().then(function (f) { return f.text(); }); }
      function writeText(name, obj) {
        return handle.getFileHandle(name, { create: true }).then(function (fh) {
          return fh.createWritable().then(function (w) {
            return w.write(JSON.stringify(obj)).then(function () { return w.close(); });
          });
        });
      }
      return {
        name: 'dir',
        load: function () {
          return entries().then(function (list) {
            var tasks = [], meta = {};
            return Promise.all(list.map(function (h) {
              if (h.kind !== 'file') return Promise.resolve();
              return readText(h).then(function (txt) {
                try {
                  var o = JSON.parse(txt);
                  if (h.name === META) meta = o || {};
                  else if (o && o.id) tasks.push(o);
                } catch (e) {}
              }).catch(function () {});
            })).then(function () {
              return { tasks: tasks, seq: meta.seq || 1, promptTpl: meta.promptTpl };
            });
          }).catch(function () { return { tasks: [], seq: 1 }; });
        },
        save: function (st) {
          return entries().then(function (list) {
            return Promise.all(list.map(function (h) { return handle.removeEntry(h.name).catch(function () {}); }))
              .then(function () {
                return Promise.all((st.tasks || []).map(function (t) {
                  return writeText(t.id + '.json', t).catch(function () {});
                }));
              }).then(function () {
                return writeText(META, { seq: st.seq || 1, promptTpl: st.promptTpl }).catch(function () {});
              });
          }).catch(function () {});
        },
        apply: function (op) {
          if (op.type === 'put') return writeText(op.task.id + '.json', op.task).catch(function () {});
          return handle.removeEntry(op.id + '.json').catch(function () {});
        },
        saveMeta: function (m) {
          return writeText(META, { seq: m.seq || 1, promptTpl: m.promptTpl }).catch(function () {});
        }
      };
    },

    /* 后端 API：GET / PUT / DELETE */
    http: function (opts) {
      var base = ((opts && opts.baseUrl) || '/api/tasks').replace(/\/$/, '');
      function call(method, url, body) {
        return fetch(url, {
          method: method,
          headers: { 'Content-Type': 'application/json' },
          body: body ? JSON.stringify(body) : undefined
        }).then(function (r) {
          if (!r.ok) throw new Error('HTTP ' + r.status);
          return r.status === 204 ? null : r.json().catch(function () { return null; });
        });
      }
      return {
        name: 'http',
        load: function () {
          return call('GET', base)
            .then(function (d) {
              return d && Array.isArray(d.tasks) ? d : { tasks: [], seq: 1 };
            })
            .catch(function () { return { tasks: [], seq: 1 }; });
        },
        save: function (st) { return call('PUT', base, st).catch(function () {}); },
        apply: function (op) {
          if (op.type === 'put') {
            return call('PUT', base + '/' + encodeURIComponent(op.task.id), op.task).catch(function () {});
          }
          return call('DELETE', base + '/' + encodeURIComponent(op.id)).catch(function () {});
        },
        saveMeta: function (m) { return call('PUT', base + '/_meta', m).catch(function () {}); }
      };
    }
  };

  function pickDir() {
    if (!window.showDirectoryPicker) return Promise.reject(new Error('当前浏览器不支持 showDirectoryPicker'));
    return window.showDirectoryPicker({ mode: 'readwrite' });
  }

  /* data.js 的读写：文件内容是 window.__MZTASK_DATA__ = {...} */
  function buildDataJs(st) {
    var d = { tasks: st.tasks || [], seq: st.seq || 1 };
    if (st.promptTpl) d.promptTpl = st.promptTpl;
    return '/* mztask-data.js —— 任务数据，改这个文件等于改初始数据 */\n' +
      'window.__MZTASK_DATA__ = ' + JSON.stringify(d, null, 2) + ';\n';
  }
  function parseDataJs(text) {
    if (!text) return null;
    /* 优先用 Function 求值，能容忍注释和格式差异 */
    try {
      var fn = new Function('window', String(text) + '\n;return window.__MZTASK_DATA__;');
      var v = fn({});
      if (v && Array.isArray(v.tasks)) return v;
    } catch (e) {}
    /* 退一步：抓 JSON 主体 */
    var m = String(text).match(/window\.__MZTASK_DATA__\s*=\s*([\s\S]*);?\s*$/);
    if (m) {
      try { var o = JSON.parse(m[1]); if (o && Array.isArray(o.tasks)) return o; } catch (e) {}
    }
    return null;
  }

  /* 记住文件/目录句柄：句柄可以存进 IndexedDB，下次打开能认出来（仍需一次授权） */
  function handleDb() { return openIdb('mztask_handles'); }
  function saveHandle(name, handle) {
    return handleDb().then(function (db) {
      return idbTx(db, ['handles'], 'readwrite', function (t) {
        t.objectStore('handles').put({ k: name, h: handle, at: Date.now() });
      });
    }).catch(function () {});
  }
  function loadHandle(name) {
    return handleDb().then(function (db) {
      return idbTx(db, ['handles'], 'readonly', function (t) {
        return idbReq(t.objectStore('handles').get(name));
      });
    }).then(function (rec) { return rec ? rec.h : null; }).catch(function () { return null; });
  }
  function clearHandle(name) {
    return handleDb().then(function (db) {
      return idbTx(db, ['handles'], 'readwrite', function (t) { t.objectStore('handles').delete(name); });
    }).catch(function () {});
  }
  /* 需要用户手势：查询/请求读写权限 */
  function ensurePermission(handle) {
    if (!handle || typeof handle.queryPermission !== 'function') return Promise.resolve(true);
    return handle.queryPermission({ mode: 'readwrite' }).then(function (st) {
      if (st === 'granted') return true;
      return handle.requestPermission({ mode: 'readwrite' }).then(function (st2) {
        return st2 === 'granted';
      });
    }).catch(function () { return false; });
  }

  function resolveAdapter(opts) {
    var a = opts.adapter;
    if (a && typeof a === 'object' && typeof a.load === 'function') return a;
    if (a === 'host') return adapters.host(opts);
    if (a === 'memory') return adapters.memory(opts);
    if (a === 'idb' || a === 'indexeddb') return adapters.idb(opts);
    if (a === 'opfs') return adapters.opfs(opts);
    if (a === 'file') return adapters.file(opts);
    if (a === 'jsfile' || a === 'js') return adapters.jsfile(opts);
    if (a === 'dir' || a === 'directory') return adapters.dir(opts);
    if (a === 'http' || a === 'api') return adapters.http(opts);
    if (a === 'local' || a === 'localStorage') return adapters.local(opts);
    /* 默认：宿主优先（exe 那种 postMessage 落盘），否则 localStorage */
    if (window.chrome && window.chrome.webview) return adapters.host(opts);
    return adapters.local(opts);
  }

  function mount(target, options) {
    injectCss();
    var el = typeof target === 'string' ? document.querySelector(target) : target;
    if (!el) throw new Error('MZTask.mount: 找不到容器 ' + target);

    var opts = Object.assign({
      title: '任务',
      enablePrompt: true,
      promptRule: DEFAULT_RULE,
      promptTpl: DEFAULT_TPL,
      storageKey: 'mztask.v1'
    }, globalDefaults, options || {});
    var adapter = resolveAdapter(opts);
    var uid = 'mzt' + Math.random().toString(36).slice(2, 8);
    var mem = { tasks: [], seq: 1 };
    var saved = { tasks: [], seq: 1 };     /* 上一次落盘的状态，用来算增量 */
    var readyResolve;
    var ready = new Promise(function (r) { readyResolve = r; });

    function data() { return mem; }
    function snap(x) { try { return JSON.parse(JSON.stringify(x)); } catch (e) { return { tasks: [], seq: 1 }; } }

    function save(d) {
      mem = d;
      if (typeof adapter.apply === 'function') {
        /* 增量：和「上次落盘的状态」比，只有变化的记录才 put，删掉的才 del */
        var byId = {}, nextIds = {};
        (saved.tasks || []).forEach(function (t) { byId[t.id] = t; });
        (d.tasks || []).forEach(function (t) {
          nextIds[t.id] = 1;
          var old = byId[t.id];
          if (!old || JSON.stringify(old) !== JSON.stringify(t)) {
            try { adapter.apply({ type: 'put', task: t }); } catch (e) {}
          }
        });
        (saved.tasks || []).forEach(function (t) {
          if (!nextIds[t.id]) { try { adapter.apply({ type: 'del', id: t.id }); } catch (e) {} }
        });
        if (typeof adapter.saveMeta === 'function') {
          try { adapter.saveMeta({ seq: d.seq, promptTpl: d.promptTpl }); } catch (e) {}
        }
        saved = snap(d);
      } else {
        try { adapter.save(d); } catch (e) {}
        saved = snap(d);
      }
      if (typeof opts.onChange === 'function') { try { opts.onChange(d.tasks || []); } catch (e) {} }
    }
    function $(id) { return document.getElementById(uid + '_' + id); }
    function getTpl() {
      var d = data();
      var t = d.promptTpl;
      return (t && String(t).trim()) ? String(t) : opts.promptTpl;
    }
    function setTpl(v) {
      var d = data();
      if (v && String(v).trim() && v !== opts.promptTpl) d.promptTpl = v;
      else delete d.promptTpl;
      save(d);
    }
    function toast(msg) {
      var t = document.getElementById(uid + '_toast');
      if (!t) { t = document.createElement('div'); t.id = uid + '_toast'; t.className = 'mzt-toast'; document.body.appendChild(t); }
      t.textContent = msg;
      t.classList.add('on');
      clearTimeout(t._t);
      t._t = setTimeout(function () { t.classList.remove('on'); }, 1900);
    }

    /* ---------- 骨架 ---------- */
    el.classList.add('mzt');
    el.innerHTML =
      '<div class="mzt-bar"><b style="color:var(--mzt-gold)">' + esc(opts.title) + '</b>' +
        '<span class="mzt-stat" id="' + uid + '_stat">—</span>' +
      '</div>' +
      '<div class="mzt-in">' +
        '<input type="text" class="mzt-title" id="' + uid + '_title" placeholder="一句话标题，例：挂机体活接入炼药成功率">' +
        '<select id="' + uid + '_kind"><option>需求</option><option>问题</option></select>' +
        '<button class="pri" id="' + uid + '_add">添加</button>' +
      '</div>' +
      '<textarea class="mzt-detail" id="' + uid + '_detail" placeholder="细节：想改成什么样、哪里难受、期望效果（可留空）"></textarea>' +
      '<div class="mzt-sec" id="' + uid + '_list"></div>' +
      '<div class="mzt-sec" id="' + uid + '_hist"></div>' +
      (opts.enablePrompt ?
        '<div class="mzt-sec">' +
          '<div class="mzt-bar"><b style="color:var(--mzt-gold)">给 agent 的 prompt</b>' +
            '<button class="pri" id="' + uid + '_gen">生成</button>' +
            '<button id="' + uid + '_copy">复制</button>' +
            '<button id="' + uid + '_export">导出 JSON</button>' +
            '<button id="' + uid + '_importBtn">导入 JSON</button>' +
            '<input type="file" id="' + uid + '_file" accept=".json,application/json" style="display:none">' +
            '<span class="mzt-stat">只带「进行中 + 待办」</span></div>' +
          '<textarea class="mzt-prompt" id="' + uid + '_prompt"></textarea>' +
          '<details class="mzt-tpl"><summary>prompt 模板（可编辑）</summary>' +
            '<div class="mzt-hint">整份模板；占位符 <code>{count}</code> 条数 · <code>{tasks}</code> 清单 · <code>{rules}</code> 规则段</div>' +
            '<textarea class="mzt-prompt" id="' + uid + '_tpl" style="min-height:200px"></textarea>' +
            '<div class="mzt-bar" style="margin-top:6px"><button id="' + uid + '_tplReset">恢复默认模板</button>' +
            '<span class="mzt-stat" id="' + uid + '_tplState"></span></div>' +
          '</details>' +
        '</div>' : '') +
      '<div class="mzt-mask" id="' + uid + '_mask"><div class="mzt-box">' +
        '<div class="h">标记为已解决 · <span id="' + uid + '_fixTitle"></span></div>' +
        '<div class="lbl">问题原因</div><textarea id="' + uid + '_cause" placeholder="根因是什么，不是表面现象"></textarea>' +
        '<div class="lbl">解决方案</div><textarea id="' + uid + '_fix" placeholder="动了哪里、机制上怎么改的、怎么验证的"></textarea>' +
        '<div class="b"><button class="pri" id="' + uid + '_fixOk">保存</button>' +
        '<button id="' + uid + '_fixSkip">先不写</button></div>' +
      '</div></div>';

    /* ---------- 渲染 ---------- */
    function renderHistory() {
      var host = $( 'hist');
      if (!host) return;
      var done = (data().tasks || []).filter(function (t) { return t.status === 'done'; });
      if (!done.length) { host.innerHTML = '<div class="mzt-sec-h">历史进度</div><div class="mzt-empty">还没有已完成的任务</div>'; return; }
      var weekAgo = new Date(new Date().getFullYear(), new Date().getMonth(), new Date().getDate() - 6).getTime();
      var week = done.filter(function (t) { return (t.updated || 0) >= weekAgo; }).length;
      var byDay = {};
      done.forEach(function (t) { var k = dayKey(t.updated || t.created); (byDay[k] = byDay[k] || []).push(t); });
      var days = Object.keys(byDay).sort().reverse();
      var html = '<div class="mzt-sec-h">历史进度</div>' +
        '<div class="mzt-hist-sum">累计完成 <b>' + done.length + '</b> 条 · 近 7 天 <b>' + week + '</b> 条</div>';
      days.forEach(function (k) {
        var arr = byDay[k].slice().sort(function (a, b) { return (b.updated || 0) - (a.updated || 0); });
        html += '<div class="mzt-hday"><span>' + k + '</span><span>' + arr.length + ' 条</span></div><ul class="mzt-hist-ul">';
        arr.forEach(function (t) { html += '<li>' + esc(t.title) + (t.kind ? '<span class="k">' + esc(t.kind) + '</span>' : '') + '</li>'; });
        html += '</ul>';
      });
      host.innerHTML = html;
    }

    function render() {
      var d = data();
      var box = $('list');
      var list = (d.tasks || []).slice().sort(function (a, b) {
        return (b.updated || 0) - (a.updated || 0) || (b.created || 0) - (a.created || 0);
      });
      var stat = { doing: 0, todo: 0, done: 0 };
      var html = '';
      ORDER.forEach(function (st) {
        var arr = list.filter(function (t) { return (t.status || 'todo') === st; });
        stat[st] = arr.length;
        var rows = '';
        arr.forEach(function (t) {
          var ops = [];
          if (st !== 'done') ops.push('<button data-op="done" data-id="' + t.id + '">完成</button>');
          if (st === 'done') ops.push('<button data-op="reopen" data-id="' + t.id + '">重开</button>');
          if (st === 'done') ops.push('<button data-op="fix" data-id="' + t.id + '">' + (t.fix ? '改方案' : '补方案') + '</button>');
          if (st === 'todo') ops.push('<button data-op="doing" data-id="' + t.id + '">开始</button>');
          if (st === 'doing') ops.push('<button data-op="todo" data-id="' + t.id + '">搁置</button>');
          ops.push('<button data-op="del" data-id="' + t.id + '">删除</button>');
          rows += '<div class="mzt-row ' + st + '"><span class="flag">' + FLAG[st] + '</span>' +
            '<div class="body"><div class="t">' + esc(t.title) + '</div>' +
            (t.detail ? '<div class="d">' + esc(t.detail) + '</div>' : '') +
            (t.cause ? '<div class="fx cause"><b>问题原因：</b>' + esc(t.cause) + '</div>'
                     : (st === 'done' ? '<div class="fx cause empty">还没有写问题原因</div>' : '')) +
            (t.fix ? '<div class="fx"><b>解决方案：</b>' + esc(t.fix) + '</div>'
                   : (st === 'done' ? '<div class="fx empty">还没有写解决方案</div>' : '')) +
            (t.source ? '<div class="src"><b>位置：</b>' + esc(t.source) + '</div>' : '') +
            '<div class="meta">' + esc(t.kind || '需求') + ' · 创建 ' + fmt(t.created || now()) +
            (t.updated && t.updated !== t.created ? ' · 更新 ' + fmt(t.updated) : '') + '</div></div>' +
            '<div class="ops">' + ops.join('') + '</div></div>';
        });
        html += '<div class="mzt-sec"><div class="mzt-sec-h">' + GROUP[st] + '（' + arr.length + '）</div>' +
          (arr.length ? '<div class="mzt-list">' + rows + '</div>' : '<div class="mzt-empty">— 空 —</div>') + '</div>';
      });
      box.innerHTML = html;
      $('stat').textContent = '进行中 ' + stat.doing + ' · 待办 ' + stat.todo + ' · 已解决 ' + stat.done;
      renderHistory();
    }

    /* ---------- 操作 ---------- */
    function addTask(t) {
      var d = data();
      d.tasks = d.tasks || [];
      var task = {
        id: t.id || ('t' + (d.seq || 1)),
        title: t.title || '(未命名)',
        detail: t.detail || '',
        kind: t.kind || '需求',
        status: t.status || 'todo',
        created: t.created || now(),
        updated: t.updated || now()
      };
      if (t.cause) task.cause = t.cause;
      if (t.fix) task.fix = t.fix;
      if (t.source) task.source = t.source;
      d.seq = Math.max(d.seq || 1, (parseInt(String(task.id).replace(/\D/g, ''), 10) || 0) + 1);
      d.tasks.push(task);
      save(d); render();
      return task;
    }

    function addFromForm() {
      var title = ($('title').value || '').trim();
      if (!title) { $('title').focus(); return null; }
      var t = addTask({ title: title, detail: ($('detail').value || '').trim(), kind: $('kind').value });
      $('title').value = ''; $('detail').value = '';
      return t;
    }

    function setStatus(id, st) {
      var d = data();
      var t = (d.tasks || []).filter(function (x) { return x.id === id; })[0];
      if (!t) return;
      t.status = st; t.updated = now();
      save(d); render();
    }

    function remove(id) {
      if (!window.confirm('删除这条任务？')) return;
      var d = data();
      d.tasks = (d.tasks || []).filter(function (x) { return x.id !== id; });
      save(d); render();
    }

    var pending = null;
    function openFix(id, complete) {
      var d = data();
      var t = (d.tasks || []).filter(function (x) { return x.id === id; })[0];
      if (!t) return;
      pending = { id: id, complete: complete };
      $('fixTitle').textContent = t.title;
      $('cause').value = t.cause || '';
      $('fix').value = t.fix || '';
      $('mask').classList.add('on');
      setTimeout(function () { $('cause').focus(); }, 30);
    }
    function closeFix() { $('mask').classList.remove('on'); pending = null; }
    function applyFix() {
      if (!pending) return;
      var c = ($('cause').value || '').trim();
      var v = ($('fix').value || '').trim();
      var d = data();
      var t = (d.tasks || []).filter(function (x) { return x.id === pending.id; })[0];
      if (t) {
        if (c) t.cause = c; else delete t.cause;
        if (v) t.fix = v; else delete t.fix;
        if (pending.complete) t.status = 'done';
        t.updated = now();
        save(d); render();
      }
      closeFix();
    }
    function skipFix() {
      if (pending && pending.complete) {
        var d = data();
        var t = (d.tasks || []).filter(function (x) { return x.id === pending.id; })[0];
        if (t) { t.status = 'done'; t.updated = now(); save(d); render(); }
      }
      closeFix();
    }

    function act(op, id) {
      if (op === 'del') return remove(id);
      if (op === 'done') return openFix(id, true);
      if (op === 'fix') return openFix(id, false);
      if (op === 'reopen') return setStatus(id, 'todo');
      if (op === 'doing') return setStatus(id, 'doing');
      if (op === 'todo') return setStatus(id, 'todo');
    }

    /* ---------- prompt ---------- */
    function buildPrompt() {
      var d = data();
      var doing = (d.tasks || []).filter(function (t) { return t.status === 'doing'; });
      var todo = (d.tasks || []).filter(function (t) { return (t.status || 'todo') === 'todo'; });
      var segs = [];
      if (doing.length) segs.push('【进行中】\n' + doing.map(function (t, i) {
        return (i + 1) + '. ' + t.title + (t.detail ? '\n   细节：' + t.detail.replace(/\n/g, ' ') : '');
      }).join('\n'));
      if (todo.length) segs.push('【待办】\n' + todo.map(function (t, i) {
        return (i + 1) + '. ' + t.title + (t.detail ? '\n   细节：' + t.detail.replace(/\n/g, ' ') : '');
      }).join('\n'));
      var tasksText = segs.length ? segs.join('\n\n') : '（暂无未完成任务）';
      return getTpl()
        .replace(/\{rules\}/g, opts.promptRule || '')
        .replace(/\{count\}/g, String(doing.length + todo.length))
        .replace(/\{tasks\}/g, tasksText);
    }

    function syncTpl() {
      var el = $('tpl');
      if (!el) return;
      el.value = getTpl();
      var st = $('tplState');
      if (!st) return;
      var miss = [];
      if (el.value.indexOf('{tasks}') < 0) miss.push('{tasks}');
      if (miss.length) { st.textContent = '⚠ 模板里没有 ' + miss.join('/') + '，生成时任务清单不会出现'; st.style.color = '#e0a34a'; }
      else { st.textContent = data().promptTpl ? '已自定义 · 自动保存' : '正在用默认模板'; st.style.color = ''; }
    }

    function copyText(text) {
      function done(ok) { toast(ok ? '✓ 已复制（' + text.length + ' 字）' : '复制失败，请手动全选复制'); }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function () { done(true); }, function () { done(false); });
      } else {
        var ta = document.createElement('textarea');
        ta.value = text; ta.style.position = 'fixed'; ta.style.left = '-9999px';
        document.body.appendChild(ta); ta.select();
        var ok = false; try { ok = document.execCommand('copy'); } catch (e) {}
        document.body.removeChild(ta); done(ok);
      }
    }

    function exportJson() {
      var d = data();
      var json = JSON.stringify(d, null, 2);
      var blob = new Blob([json], { type: 'application/json' });
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = '任务板.json';
      a.click();
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 2000);
      return json;
    }

    function importJson(text) {
      var obj = JSON.parse(text);
      if (!obj || !Array.isArray(obj.tasks)) throw new Error('不是任务板备份');
      var cur = data();
      cur.tasks = cur.tasks || [];
      var byId = {};
      cur.tasks.forEach(function (t) { byId[t.id] = t; });
      var added = 0, updated = 0;
      obj.tasks.forEach(function (t) {
        if (!t || !t.id) return;
        var old = byId[t.id];
        if (!old) { cur.tasks.push(t); added++; }
        else if ((t.updated || 0) > (old.updated || 0)) {
          old.title = t.title; old.detail = t.detail; old.kind = t.kind;
          old.status = t.status; old.cause = t.cause; old.fix = t.fix;
          old.updated = t.updated; updated++;
        }
      });
      cur.seq = Math.max(cur.seq || 1, obj.seq || 1, cur.tasks.length + 1);
      if (typeof obj.promptTpl === 'string' && obj.promptTpl.trim()) cur.promptTpl = obj.promptTpl;
      save(cur); render(); syncTpl();
      return { added: added, updated: updated };
    }

    /* ---------- 事件 ---------- */
    $('add').addEventListener('click', addFromForm);
    $('list').addEventListener('click', function (e) {
      var b = e.target && e.target.closest ? e.target.closest('button[data-op]') : null;
      if (b) act(b.getAttribute('data-op'), b.getAttribute('data-id'));
    });
    $('fixOk').addEventListener('click', applyFix);
    $('fixSkip').addEventListener('click', skipFix);
    $('mask').addEventListener('click', function (e) { if (e.target === this) closeFix(); });

    document.addEventListener('keydown', function (e) {
      if (e.key !== 'Escape') return;
      if ($('mask') && $('mask').classList.contains('on')) closeFix();
    });

    if (opts.enablePrompt) {
      $('gen').addEventListener('click', function () { $('prompt').value = buildPrompt(); });
      $('copy').addEventListener('click', function () {
        var v = $('prompt').value;
        if (!v.trim()) { toast('先点「生成」'); return; }
        copyText(v);
      });
      $('export').addEventListener('click', exportJson);
      $('importBtn').addEventListener('click', function () { $('file').click(); });
      $('file').addEventListener('change', function () {
        var f = this.files && this.files[0];
        if (!f) return;
        var rd = new FileReader();
        var self = this;
        rd.onload = function () {
          try { var r = importJson(rd.result); toast('导入完成：新增 ' + r.added + '，更新 ' + r.updated); }
          catch (e) { toast('导入失败：' + e.message); }
          self.value = '';
        };
        rd.readAsText(f, 'utf-8');
      });
      var tplTimer = null;
      $('tpl').addEventListener('input', function () {
        var v = this.value;
        clearTimeout(tplTimer);
        tplTimer = setTimeout(function () { setTpl(v); }, 400);
      });
      $('tpl').addEventListener('blur', function () { clearTimeout(tplTimer); setTpl(this.value); syncTpl(); });
      $('tplReset').addEventListener('click', function () { setTpl(''); syncTpl(); toast('已恢复默认模板'); });
      syncTpl();
    }

    render();
    adapter.load().then(function (d) {
      if (d && Array.isArray(d.tasks)) mem = d;
      saved = snap(mem);          /* 以加载到的状态为增量基线 */
      render();
      syncTpl();
      readyResolve();
    }).catch(function () { readyResolve(); });

    return {
      version: VERSION,
      ready: ready,
      adapter: adapter.name,
      el: el,
      add: addTask,
      getTasks: function () { return data().tasks || []; },
      setStatus: setStatus,
      remove: function (id) {
        var d = data();
        d.tasks = (d.tasks || []).filter(function (x) { return x.id !== id; });
        save(d); render();
      },
      prompt: buildPrompt,
      exportJson: exportJson,
      /* 导出成可以直接引入的 data.js：window.__MZTASK_DATA__ = {...} */
      exportDataJs: function () {
        var d = data();
        var st = { tasks: d.tasks || [], seq: d.seq || 1 };
        if (d.promptTpl) st.promptTpl = d.promptTpl;
        return '/* mztask-data.js —— 由任务板导出，覆盖同名文件即可作为新的初始数据 */\n' +
          'window.__MZTASK_DATA__ = ' + JSON.stringify(st, null, 2) + ';\n';
      },
      importJson: importJson,
      replace: function (tasks) {
        var maxId = 0;
        (tasks || []).forEach(function (t) {
          var n = parseInt(String(t.id || '').replace(/\D/g, ''), 10) || 0;
          if (n > maxId) maxId = n;
        });
        save({ tasks: tasks || [], seq: maxId + 1 });
        render();
      },
      refresh: render,
      clear: function () { save({ tasks: [], seq: 1 }); render(); syncTpl(); }
    };
  }


  /* ---------- 全局标注：宿主页面上放个按钮，调 MZTask.annotate().toggle ----------
     用法：
       var ann = MZTask.annotate({ board: board });        // 结果写进这个任务板
       btn.onclick = ann.toggle;                            // 你自己的按钮
     也可以不传 board，用 onAdd(task) 自己处理。 */
  var annSession = null;
  function annotate(opts) {
    opts = opts || {};
    if (annSession) { annSession.setOptions(opts); return annSession; }
    injectCss();

    var hl = document.createElement('div');
    hl.className = 'mzt-ann-hl';
    document.body.appendChild(hl);

    var mask = document.createElement('div');
    mask.className = 'mzt-mask';
    mask.innerHTML =
      '<div class="mzt-box">' +
        '<div class="h">标注 → 任务</div>' +
        '<div class="lbl" id="mzt_annSel" style="word-break:break-all"></div>' +
        '<div class="lbl">标题</div><textarea id="mzt_annTitle" style="min-height:44px" placeholder="一句话说明这里要改什么"></textarea>' +
        '<div class="lbl">细节</div><textarea id="mzt_annDetail" placeholder="想改成什么样、哪里难受、期望效果（可留空）"></textarea>' +
        '<div class="b"><button class="pri" id="mzt_annOk">添加任务</button>' +
        '<button id="mzt_annCancel">取消</button></div>' +
      '</div>';
    document.body.appendChild(mask);

    var annotating = false, target = null, options = opts;
    var $ = function (id) { return document.getElementById('mzt_' + id); };

    /* 宿主自己的触发按钮（点它开关标注模式）—— 标注模式下不能被拦截 */
    function triggerEls() {
      var t = options.trigger;
      if (!t) return [];
      var list = Array.isArray(t) ? t : [t];
      var out = [];
      list.forEach(function (x) {
        if (!x) return;
        if (typeof x === 'string') {
          try { out = out.concat(Array.prototype.slice.call(document.querySelectorAll(x))); } catch (e) {}
        } else if (x.nodeType === 1) out.push(x);
      });
      return out;
    }
    function isTrigger(el) {
      return triggerEls().some(function (b) { return b === el || b.contains(el); });
    }
    function bindTrigger() {
      triggerEls().forEach(function (b) {
        if (b.__mztBound) return;
        b.__mztBound = true;
        b.addEventListener('click', function () { toggle(); });
      });
    }

    function selectorOf(el) {
      if (!el || el.nodeType !== 1) return '';
      var parts = [], node = el, guard = 0;
      while (node && node.nodeType === 1 && guard++ < 8) {
        var s = node.tagName.toLowerCase();
        if (node.id) { s += '#' + node.id; parts.unshift(s); break; }
        var cls = (node.className || '').toString().trim().split(/\s+/).filter(Boolean).slice(0, 2);
        if (cls.length) s += '.' + cls.join('.');
        parts.unshift(s);
        if (node === document.body) break;
        node = node.parentElement;
      }
      return parts.join(' > ');
    }
    function hlOn(el) {
      if (!el || !el.getBoundingClientRect) return;
      var r = el.getBoundingClientRect();
      hl.style.left = r.left + 'px'; hl.style.top = r.top + 'px';
      hl.style.width = r.width + 'px'; hl.style.height = r.height + 'px';
      hl.classList.add('on');
    }
    function hlOff() { hl.classList.remove('on'); }

    function move(e) {
      if (!annotating) return;
      var el = e.target;
      if (!el || el === hl || el === document.body) { hlOff(); return; }
      hlOn(el);
    }
    function click(e) {
      if (!annotating) return;
      var el = e.target;
      if (!el || el === hl || el === document.body) return;
      if (mask.contains(el)) return;      /* 标注弹框自己的按钮不拦 */
      if (isTrigger(el)) return;          /* 宿主自己的触发按钮不拦，否则点它关不掉 */
      e.preventDefault(); e.stopPropagation();
      target = el;
      $('annSel').textContent = '位置：' + selectorOf(el);
      $('annTitle').value = '';
      $('annDetail').value = '';
      mask.classList.add('on');
      setTimeout(function () { $('annTitle').focus(); }, 30);
    }
    function start() {
      if (annotating) return;
      annotating = true;
      document.body.classList.add('mzt-annotating');
      document.addEventListener('mousemove', move, true);
      document.addEventListener('click', click, true);
      if (typeof options.onStart === 'function') { try { options.onStart(); } catch (e) {} }
    }
    function stop() {
      if (!annotating) return;
      annotating = false;
      document.body.classList.remove('mzt-annotating');
      hlOff();
      document.removeEventListener('mousemove', move, true);
      document.removeEventListener('click', click, true);
      if (typeof options.onStop === 'function') { try { options.onStop(); } catch (e) {} }
    }
    function toggle() { if (annotating) stop(); else start(); }

    function save() {
      var title = ($('annTitle').value || '').trim();
      if (!title) { $('annTitle').focus(); return; }
      var detail = ($('annDetail').value || '').trim();
      var sel = target ? selectorOf(target) : '';
      var task = {
        title: title, detail: detail, kind: '问题', status: 'todo',
        created: Date.now(), updated: Date.now(), source: sel
      };
      if (options.board && typeof options.board.add === 'function') {
        /* 交给任务板生成 id（和普通任务同一套 t1/t2 规则，避免两套 id 混用） */
        options.board.add(task);
      } else {
        if (!task.id) task.id = 't' + Date.now().toString(36);
        if (typeof options.onAdd === 'function') {
          try { options.onAdd(task); } catch (e) {}
        }
      }
      mask.classList.remove('on');
      stop();
      target = null;
    }

    $('annOk').addEventListener('click', save);
    $('annCancel').addEventListener('click', function () { mask.classList.remove('on'); });
    mask.addEventListener('click', function (e) { if (e.target === this) mask.classList.remove('on'); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        if (mask.classList.contains('on')) mask.classList.remove('on');
        else if (annotating) stop();
      }
    });

    annSession = {
      start: start, stop: stop, toggle: toggle,
      isOn: function () { return annotating; },
      setOptions: function (o) { options = Object.assign(options, o || {}); bindTrigger(); },
      destroy: function () { stop(); if (hl.parentNode) hl.parentNode.removeChild(hl); if (mask.parentNode) mask.parentNode.removeChild(mask); annSession = null; }
    };
    bindTrigger();
    return annSession;
  }

  /* ---------- 文件持久化：JSONL 追加日志（File System Access API） ----------
     "改"也是追加：{"t":"update","id":"t1","fields":{...}}，读取时按顺序重放。
     用法：
       var handle = await MZTask.pickFile();        // 用户选一个 .jsonl
       var fs = MZTask.bindFile(board, handle);     // 接管持久化，之后每次改动追加一行
       await fs.compact();                          // 可选：把日志压成一份快照
     注意：需要安全上下文（https 或 http://localhost），file:// 打不开这个 API。 */
  function replay(text) {
    var map = {}, order = [], seq = 1;
    String(text || '').split('\n').forEach(function (ln) {
      if (!ln.trim()) return;
      var op;
      try { op = JSON.parse(ln); } catch (e) { return; }
      if ((op.t === 'add' || op.t === 'upsert') && op.task && op.task.id) {
        if (!map[op.task.id]) order.push(op.task.id);
        map[op.task.id] = op.t === 'upsert' && map[op.task.id]
          ? Object.assign({}, map[op.task.id], op.task)
          : op.task;
        var n = parseInt(String(op.task.id).replace(/\D/g, ''), 10) || 0;
        if (n >= seq) seq = n + 1;
      } else if (op.t === 'update' && op.id && map[op.id]) {
        Object.assign(map[op.id], op.fields || {});
      } else if (op.t === 'delete' && op.id) {
        delete map[op.id];
        order = order.filter(function (x) { return x !== op.id; });
      }
    });
    return { tasks: order.map(function (id) { return map[id]; }), seq: seq };
  }

  function cloneTasks(ts) { try { return JSON.parse(JSON.stringify(ts || [])); } catch (e) { return []; } }

  function diffTasks(prev, next) {
    var byId = {}, nextIds = {}, ops = [];
    (prev || []).forEach(function (t) { byId[t.id] = t; });
    (next || []).forEach(function (t) {
      nextIds[t.id] = 1;
      var old = byId[t.id];
      if (!old) { ops.push({ t: 'add', at: Date.now(), task: t }); return; }
      var fields = {};
      Object.keys(t).forEach(function (k) {
        if (k === 'updated') return;
        if (JSON.stringify(old[k]) !== JSON.stringify(t[k])) fields[k] = t[k];
      });
      if (Object.keys(fields).length) ops.push({ t: 'update', at: Date.now(), id: t.id, fields: fields });
    });
    (prev || []).forEach(function (t) {
      if (!nextIds[t.id]) ops.push({ t: 'delete', at: Date.now(), id: t.id });
    });
    return ops;
  }

  function appendOps(handle, ops) {
    if (!ops || !ops.length) return Promise.resolve();
    var text = ops.map(function (o) { return JSON.stringify(o); }).join('\n') + '\n';
    return (async function () {
      var file = await handle.getFile();
      var w = await handle.createWritable({ keepExistingData: true });
      await w.seek(file.size);          /* 定位到末尾，只追加，不重写前面 */
      await w.write(text);
      await w.close();
    })();
  }

  async function pickFile(suggestedName) {
    if (!window.showSaveFilePicker) throw new Error('当前浏览器不支持 File System Access API（需要 Edge/Chrome 且 https 或 localhost）');
    return await window.showSaveFilePicker({
      suggestedName: suggestedName || 'mztask-data.jsonl',
      types: [{ description: '任务日志', accept: { 'application/x-ndjson': ['.jsonl'] } }]
    });
  }

  async function openFile() {
    if (!window.showOpenFilePicker) throw new Error('当前浏览器不支持 File System Access API');
    var arr = await window.showOpenFilePicker({
      multiple: false,
      types: [{ description: '任务日志', accept: { 'application/x-ndjson': ['.jsonl'], 'application/json': ['.json'] } }]
    });
    return arr[0];
  }

  function bindFile(board, handle, opts) {
    opts = opts || {};
    var suppress = false, last = [];
    var queue = Promise.resolve();
    var stat = { writes: 0, ops: 0, error: null };

    function enqueue(ops) {
      if (!ops.length) return queue;
      stat.ops += ops.length;
      queue = queue.then(function () {
        return appendOps(handle, ops).then(function () { stat.writes++; },
          function (e) { stat.error = String(e && e.message || e); });
      });
      return queue;
    }

    function syncNow() {
      if (suppress) return;
      var now = cloneTasks(board.getTasks());
      enqueue(diffTasks(last, now));
      last = now;
    }

    /* 包住会改数据的方法，调用后把差异追加到文件 */
    ['add', 'setStatus', 'remove', 'replace', 'importJson', 'clear'].forEach(function (k) {
      var orig = board[k];
      if (typeof orig !== 'function') return;
      board[k] = function () {
        var r = orig.apply(board, arguments);
        try { syncNow(); } catch (e) {}
        return r;
      };
    });

    var ready = (async function () {
      var file = await handle.getFile();
      var text = await file.text();
      var data = replay(text);
      suppress = true;
      if (data.tasks.length) board.replace(data.tasks);
      suppress = false;
      last = cloneTasks(board.getTasks());
      if (!text.trim() && last.length) {
        await enqueue(last.map(function (t) { return { t: 'add', at: Date.now(), task: t }; }));
      }
    })();

    return {
      handle: handle,
      ready: ready,
      stat: stat,
      sync: function () { try { syncNow(); } catch (e) {} return queue; },
      flush: function () { return queue; },
      compact: async function () {
        await queue;
        var tasks = board.getTasks();
        var lines = tasks.map(function (t) { return JSON.stringify({ t: 'add', at: Date.now(), task: t }); });
        var w = await handle.createWritable();     /* 压缩：整体重写成快照 */
        await w.write(lines.join('\n') + (lines.length ? '\n' : ''));
        await w.close();
        last = cloneTasks(tasks);
        stat.writes++;
        return lines.length;
      }
    };
  }

  /* 全局默认配置：任何页面先调一次，之后所有 mount 都按这个来。
     MZTask.config({ adapter: 'idb', storageKey: 'myapp.tasks' });
     mount 里传的参数优先级更高。 */
  var globalDefaults = {};
  function config(o) {
    if (o && typeof o === 'object') globalDefaults = Object.assign(globalDefaults, o);
    return Object.assign({}, globalDefaults);
  }

  return { mount: mount, config: config, annotate: annotate, adapters: adapters, pickFile: pickFile, pickDir: pickDir, saveHandle: saveHandle, loadHandle: loadHandle, clearHandle: clearHandle, ensurePermission: ensurePermission, openFile: openFile, bindFile: bindFile, replay: replay, diffTasks: diffTasks, version: VERSION, DEFAULT_RULE: DEFAULT_RULE, DEFAULT_TPL: DEFAULT_TPL };
});
