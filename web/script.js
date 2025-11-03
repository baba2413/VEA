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
  const li = document.createElement("li");
  li.className = "video-item";
  li.dataset.id = item.id;

  const thumb = document.createElement("div");
  thumb.className = "video-thumb";

  //썸네일 이미지 element 준비
  const img = document.createElement("img");
  img.style.display = "none"; // 로딩 전까지 숨김
  thumb.appendChild(img);

  const meta = document.createElement("div");
  meta.className = "video-meta";

  const name = document.createElement("div");
  name.className = "video-name";
  name.title = item.file.name;
  name.textContent = item.file.name;

  const info = document.createElement("div");
  info.className = "video-info";
  info.textContent = `${formatBytes(item.file.size)}`;

  meta.append(name, info);

  const badge = document.createElement("span");
  badge.className = "badge";
  badge.textContent = item.file.type.replace("video/", "") || "video";

  //삭제 버튼
  const delBtn = document.createElement("button");
  delBtn.className = "delete-btn";
  delBtn.innerHTML = "🗑️";

  delBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    state.items = state.items.filter(v => v.id !== item.id);
    li.remove();
    updateCount();
  });

  li.append(thumb, meta, badge, delBtn);
  els.videoList.appendChild(li);

  //항목 클릭하면 재생 및 분석
  li.addEventListener("click", () => {
    player.src = item.url;
    player.style.display = "block";
    player.play();

    //영상 제목 표시
    document.getElementById("videoTitle").textContent = item.file.name;

    //설명칸 초기화(요약 가져오기)
    document.getElementById("videoDesc").textContent = "";

    analyzeVideo(item.file);
  });


  //썸네일 불러오기
  generateThumbnail(item.file, item.url, (dataURL) => {
    img.src = dataURL;
    img.style.display = "block";
  });
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
}


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
    const row = rows[index]; // 0~6행

    //점수는 2열
    const scoreCell = row.children[1];
    scoreCell.textContent = data.scores[key] ?? "";

    //근거(details)는 3열
    const detailCell = row.children[2];
    detailCell.textContent = data.details[key] ?? "";
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
