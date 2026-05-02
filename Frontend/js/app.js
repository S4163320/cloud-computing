//const API_BASE = "http://184.72.170.126:5000"; //EC2
const API_BASE = "https://tq99cxx1oc.execute-api.us-east-1.amazonaws.com/prod"; //Lambda


function saveUser(user) {
  localStorage.setItem("music_user", JSON.stringify(user));
}

function getUser() {
  return JSON.parse(localStorage.getItem("music_user"));
}

function logout() {
  localStorage.removeItem("music_user");
  window.location.href = "login.html";
}


const messageTimeouts = {};

function showMessage(elementId, text, isSuccess = false) {
  const el = document.getElementById(elementId);
  if (!el) return;

  if (messageTimeouts[elementId]) {
    clearTimeout(messageTimeouts[elementId]);
  }

  el.textContent = text;
  el.classList.add("show");

  if (isSuccess) {
    el.classList.add("success-card");
  } else {
    el.classList.remove("success-card");
  }

  messageTimeouts[elementId] = setTimeout(() => {
    clearMessage(elementId);
  }, 3000);
}

function clearMessage(elementId) {
  const el = document.getElementById(elementId);
  if (!el) return;

  el.textContent = "";
  el.classList.remove("show");
  el.classList.remove("success-card");

  if (messageTimeouts[elementId]) {
    clearTimeout(messageTimeouts[elementId]);
    delete messageTimeouts[elementId];
  }
}

async function login() {
  const email = document.getElementById("loginEmail").value.trim();
  const password = document.getElementById("loginPassword").value.trim();
  const message = document.getElementById("loginMessage");

  message.textContent = "";
  message.classList.remove("show");

  try {
    const res = await fetch(`${API_BASE}/login`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ email, password })
    });

    const data = await res.json();

    if (!data.success) {
      message.textContent = "email or password is invalid";
      message.classList.add("show");
      return;
    }

    saveUser(data);
    window.location.href = "main.html";
  } catch (error) {
    message.textContent = "Unable to connect to backend";
    message.classList.add("show");
    console.error(error);
  }
}

async function registerUser() {
  const email = document.getElementById("registerEmail").value.trim();
  const user_name = document.getElementById("registerUsername").value.trim();
  const password = document.getElementById("registerPassword").value.trim();
  const message = document.getElementById("registerMessage");

  message.textContent = "";
  message.classList.remove("show");

  try {
    const res = await fetch(`${API_BASE}/register`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ email, user_name, password })
    });

    const data = await res.json();

    if (!data.success) {
      message.textContent = data.message;
      message.classList.add("show");
      return;
    }

    window.location.href = "login.html";
  } catch (error) {
    message.textContent = "Unable to connect to backend";
    message.classList.add("show");
    console.error(error);
  }
}

function renderSongs(containerId, songs, isSubscription = false) {
  const container = document.getElementById(containerId);

  if (!songs.length) {
    container.innerHTML = `<p class="empty-state">${
      isSubscription ? "No subscriptions yet." : "No result is retrieved. Please query again"
    }</p>`;
    return;
  }

  container.innerHTML = songs.map(song => `
    <div class="song-card">
      <img src="${song.image_url}" alt="${song.artist}">
      <div class="song-info">
        <strong>${song.title}</strong>
        <div class="song-meta">
          Artist: ${song.artist}<br>
          Album: ${song.album}<br>
          Year: ${song.year}
        </div>
      </div>
      ${
        isSubscription
          ? `<button class="remove-btn" onclick="removeSubscription('${song.song_id}')">Remove</button>`
          : `<button onclick="subscribeSongEncoded('${encodeURIComponent(JSON.stringify(song))}')">Subscribe</button>`
      }
    </div>
  `).join("");
}

function subscribeSongEncoded(encodedSong) {
  const song = JSON.parse(decodeURIComponent(encodedSong));
  console.log("Subscribe clicked:", song);
  subscribeSong(song);
}

async function loadSubscriptions() {
  const user = getUser();
  const res = await fetch(`${API_BASE}/subscriptions?email=${encodeURIComponent(user.email)}`);
  const data = await res.json();
  renderSongs("subscriptionsContainer", data.subscriptions || [], true);
}

async function querySongs() {
  const title = document.getElementById("queryTitle").value.trim();
  const year = document.getElementById("queryYear").value.trim();
  const artist = document.getElementById("queryArtist").value.trim();
  const album = document.getElementById("queryAlbum").value.trim();

  clearMessage("queryMessage");
  clearMessage("actionMessage");

  if (!title && !year && !artist && !album) {
    showMessage("queryMessage", "At least one field must be completed");
    return;
  }

  const params = new URLSearchParams({ title, year, artist, album });
  const res = await fetch(`${API_BASE}/songs?${params.toString()}`);
  const data = await res.json();

  if (!data.success) {
    showMessage("queryMessage", data.message);
    document.getElementById("resultsContainer").innerHTML = "";
    return;
  }

  renderSongs("resultsContainer", data.songs || []);
}

async function subscribeSong(song) {
  const user = getUser();
  const songImageKey = song.img_url || song.image_key || song.s3_key || "";

  clearMessage("queryMessage");
  clearMessage("actionMessage");

  const payload = {
    email: user.email,
    artist: song.artist,
    title: song.title,
    album: song.album,
    year: song.year,
    img_url: songImageKey
  };
  console.log("POST /subscriptions payload:", payload);

  const res = await fetch(`${API_BASE}/subscriptions`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload)
  });

  const data = await res.json();
  console.log("POST /subscriptions response:", data);

  if (data.success) {
    showMessage("actionMessage", "Song subscribed successfully", true);
    loadSubscriptions();
  } else {
    showMessage("queryMessage", data.message || "Subscription failed");
  }
}

async function removeSubscription(songId) {
  const user = getUser();

  clearMessage("subscriptionMessage");

  const res = await fetch(`${API_BASE}/subscriptions/${encodeURIComponent(user.email)}/${encodeURIComponent(songId)}`, {
    method: "DELETE"
  });

  const data = await res.json();

  if (data.success) {
    showMessage("subscriptionMessage", "Song removed successfully", true);
    loadSubscriptions();
  } else {
    showMessage("subscriptionMessage", data.message || "Remove failed");
  }
}

function loadMainPage() {
  const user = getUser();
  if (!user) {
    window.location.href = "login.html";
    return;
  }

  document.getElementById("userName").textContent = user.user_name;
  loadSubscriptions();
}