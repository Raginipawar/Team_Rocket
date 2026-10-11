importScripts("https://www.gstatic.com/firebasejs/10.12.0/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/10.12.0/firebase-messaging-compat.js");

firebase.initializeApp({
  apiKey: "AIzaSyCu6ZK-RC-bxjBbFxWKeEBzSFDWnftd1G0",
  authDomain: "golden-hour-39601.firebaseapp.com",
  projectId: "golden-hour-39601",
  storageBucket: "golden-hour-39601.firebasestorage.app",
  messagingSenderId: "901244540641",
  appId: "1:901244540641:web:eab70638d2d17455e949a0",
});

const messaging = firebase.messaging();

// Shows a notification when the tab is closed/backgrounded -- the whole
// point of push ("even if the screen is not currently on").
messaging.onBackgroundMessage((payload) => {
  const { title, body } = payload.notification || {};
  self.registration.showNotification(title || "GoldenHour", {
    body: body || "",
    icon: "/icons/icon-192.png",
    data: payload.data || {},
  });
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow("/"));
});
