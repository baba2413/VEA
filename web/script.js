//캐시 변수
const summaryCache = new Map();

function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return "-";
  const u = ["B","KB","MB","GB","TB"];
  let i = 0, n = bytes;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(n >= 100 ? 0 : n >= 10 ? 1 : 2)} ${u[i]}`;
}

function formatTime(secs) {
  if (!Number.isFinite(secs)) return "길이 계산 중…";
  const s = Math.floor(secs % 60).toString().padStart(2, "0");
  const m = Math.floor((secs / 60) % 60).toString().padStart(2, "0");
  const h = Math.floor(secs / 3600);
  return h ? `${h}:${m}:${s}` : `${m}:${s}`;
}

const els = {
  loadBtn: document.getElementById("loadBtn"),
  fileInput: document.getElementById("fileInput"),
  videoList: document.getElementById("videoList"),
  videoCount: document.getElementById("videoCount"),
};

const state = {
  items: [],
};

els.loadBtn.addEventListener("click", () => els.fileInput.click());

els.fileInput.addEventListener("change", (e) => {
  const files = Array.from(e.target.files || []);
  const videos = files.filter(f => f.type.startsWith("video/"));
  if (!videos.length) return;

  const existingKey = new Set(state.items.map(i => `${i.file.name}-${i.file.size}`));

  for (const file of videos) {
    const key = `${file.name}-${file.size}`;
    if (existingKey.has(key)) continue;

    const url = URL.createObjectURL(file);
    const id = crypto.randomUUID();
    const item = { id, file, url, duration: undefined };
    state.items.push(item);
    renderItem(item);
    probeDuration(item);
  }

  updateCount();
  els.fileInput.value = "";
});

function probeDuration(item) {
  const v = document.createElement("video");
  v.preload = "metadata";
  v.muted = true;
  v.src = item.url;

  v.addEventListener("loadedmetadata", () => {
    item.duration = v.duration;
    const row = document.querySelector(`[data-id="${item.id}"]`);
    if (row) {
      const info = row.querySelector(".video-info");
      if (info) info.textContent = `${formatTime(item.duration)} • ${formatBytes(item.file.size)}`;
    }
    v.removeAttribute("src");
    v.load();
  }, { once: true });

  v.addEventListener("error", () => {
    const row = document.querySelector(`[data-id="${item.id}"]`);
    if (row) {
      const info = row.querySelector(".video-info");
      if (info) info.textContent = `${formatBytes(item.file.size)}`;
    }
  }, { once: true });
}

function renderItem(item) {
  const tbody = document.getElementById("videoListBody");

  const tr = document.createElement("tr");
  tr.dataset.id = item.id;

  //썸네일 준비
  const thumbTd = document.createElement("td");
  const img = document.createElement("img");
  img.className = "video-thumb-small";
  thumbTd.appendChild(img);

  //썸네일 생성되면 넣어줌
  generateThumbnail(item.file, item.url, (dataURL) => {
    img.src = dataURL;
  });

  //점수 7개 열
  const fields = ["topic","sexuality","violence","horror","drugs","language","imitable"];
  const scoreTds = {};

  fields.forEach(key => {
    const td = document.createElement("td");
    td.textContent = "";
    scoreTds[key] = td;
    tr.appendChild(td);
  });

  //삭제 버튼
  const delTd = document.createElement("td");
  const delBtn = document.createElement("button");
  delBtn.className = "delete-btn";
  delBtn.innerHTML = "🗑️";

  delBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    state.items = state.items.filter(v => v.id !== item.id);
    tr.remove();
    updateCount();
  });
  delTd.appendChild(delBtn);

  tr.appendChild(thumbTd);
  fields.forEach(k => tr.appendChild(scoreTds[k]));
  tr.appendChild(delTd);

  //항목 클릭하면 재생 및 분석
  tr.addEventListener("click", () => {
    player.src = item.url;
    player.style.display = "block";
    player.play();

    document.getElementById("videoTitle").textContent = item.file.name;
    document.getElementById("videoDesc").textContent = "";

    analyzeVideo(item.file); 
  });

  tbody.appendChild(tr);

  //테이블용 점수 셀들을 item에 저장
  item.scoreCells = scoreTds;
}

//캐시 생성
function buildCacheKey(file) {
  return [
    file.name,
    file.size,
    file.lastModified
  ].join("|");
}

/*영상 전송 및 분석*/
async function analyzeVideo(file) {
  const filename = file.name;
  const cacheKey = buildCacheKey(file);

  const descEl = document.getElementById("videoDesc");
  descEl.textContent = "🔍 분석 중…";

  //프론트 캐시 먼저 확인
  if (summaryCache.has(cacheKey)) {
    const data = summaryCache.get(cacheKey);
    descEl.textContent = data.content_summary || "(설명 없음)";
    fillResultTable(data);
    return;
  }

  //서버 캐시 확인
  let cached = await fetch(`http://127.0.0.1:5001/api/results/${encodeURIComponent(filename)}`);
  if (cached.ok) {
    const data = await cached.json();
    summaryCache.set(cacheKey, data);
    descEl.textContent = data.content_summary || "(설명 없음)";
    fillResultTable(data);
    return; 
  }

  //서버에 새로운 분석 요청
  const form = new FormData();
  form.append("video", file, filename);

  const res = await fetch("http://127.0.0.1:5001/api/analyze/summary?filename=" + encodeURIComponent(filename), {
    method: "POST",
    body: form
  });

  const data = await res.json();

  //프론트 캐시에 저장
  summaryCache.set(cacheKey, data);

  descEl.textContent = data.content_summary || "(설명 없음)";
  fillResultTable(data);

  const item = state.items.find(i => i.file.name === file.name && i.file.size === file.size);
  if (item) {
    applyScoresToList(item, data);
  }
}

function applyScoresToList(item, data) {
  if (!item.scoreCells) return;

  Object.entries(data.scores).forEach(([key, val]) => {
    if (item.scoreCells[key]) {
      item.scoreCells[key].textContent = val;
    }
  });
}

/* 각 표 점수 채우기 */
function fillResultTable(data) {
  const scoreKeys = [
    "topic", 
    "sexuality", 
    "violence", 
    "horror", 
    "drugs", 
    "language", 
    "imitable"
  ];

  const table = document.getElementById("resultTable");
  const rows = table.querySelectorAll("tbody tr");

  scoreKeys.forEach((key, index) => {
    const row = rows[index];
    row.children[1].textContent = data.scores[key] ?? "";
    row.children[2].textContent = data.details[key] ?? "";

    //피드백 버튼
    const feedbackTd = row.children[3];
    feedbackTd.innerHTML = ""; 

    const btn = document.createElement("button");
    btn.textContent = "작성하기";
    btn.className = "btn mini";
    btn.style.padding = "4px 8px";
    btn.style.fontSize = "11px";

    btn.addEventListener("click", () => {
      openFeedbackEditor(btn, key);
    });

    feedbackTd.appendChild(btn);
  });
}


function updateCount() {
  els.videoCount.textContent = `${state.items.length}개`;
}

window.addEventListener("beforeunload", () => {
  state.items.forEach(i => URL.revokeObjectURL(i.url));
});


//1초 기준으로 썸네일 생성
function generateThumbnail(file, url, callback) {
  const video = document.createElement("video");
  video.src = url;
  video.muted = true;
  video.preload = "auto";

  video.addEventListener("loadedmetadata", () => {
    const targetTime = video.duration > 1 ? 1 : 0.1;
    video.currentTime = targetTime;
  });

  video.addEventListener("seeked", () => {
    const canvas = document.createElement("canvas");
    canvas.width = 160;
    canvas.height = 90;

    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const dataURL = canvas.toDataURL("image/jpeg", 0.8);
    callback(dataURL);
  }, { once: true });
}

/* 피드백 상호작용 버튼 */
let activeEditor = null;

function openFeedbackEditor(button, categoryKey) {
  if (activeEditor) {
    activeEditor.remove();
    activeEditor = null;
  }

  const editor = document.createElement("div");
  editor.className = "feedback-editor";

  editor.innerHTML = `
    <textarea placeholder="피드백을 입력하세요"></textarea>
    <div class="actions">
      <button class="confirm">확인</button>
      <button class="cancel">취소</button>
    </div>
  `;

  document.body.appendChild(editor);

  //기본 위치 버튼 바로 아래
  const rect = button.getBoundingClientRect();
  let x = rect.left + window.scrollX;
  let y = rect.bottom + window.scrollY;

  //에디터 크기 계산
  const editorWidth = editor.offsetWidth;
  const editorHeight = editor.offsetHeight;

  const screenWidth = window.innerWidth;
  const screenHeight = window.innerHeight;

  //오른쪽 넘치면 왼쪽으로 이동
  if (x + editorWidth > screenWidth - 10) {
    x = screenWidth - editorWidth - 10;
  }

  //아래 넘치면 위로 이동
  if (y + editorHeight > screenHeight - 10) {
    y = rect.top + window.scrollY - editorHeight - 10;
  }

  //완전히 화면 밖으로 못나가게 최소값 지정
  if (x < 10) x = 10;
  if (y < 10) y = 10;

  editor.style.left = x + "px";
  editor.style.top = y + "px";

  activeEditor = editor;

  // 버튼 기능
  const textarea = editor.querySelector("textarea");
  const confirmBtn = editor.querySelector(".confirm");
  const cancelBtn = editor.querySelector(".cancel");

  confirmBtn.addEventListener("click", () => {
    const text = textarea.value.trim();
    if (text) {
      console.log(`피드백 저장됨 (${categoryKey}):`, text);
      editor.remove();
      activeEditor = null;
    }
  });

  cancelBtn.addEventListener("click", () => {
    editor.remove();
    activeEditor = null;
  });
}
