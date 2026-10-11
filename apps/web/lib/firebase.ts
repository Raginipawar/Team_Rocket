"use client";

import { initializeApp, getApps } from "firebase/app";
import { getMessaging, getToken, isSupported } from "firebase/messaging";

const firebaseConfig = {
  apiKey: "AIzaSyCu6ZK-RC-bxjBbFxWKeEBzSFDWnftd1G0",
  authDomain: "golden-hour-39601.firebaseapp.com",
  projectId: "golden-hour-39601",
  storageBucket: "golden-hour-39601.firebasestorage.app",
  messagingSenderId: "901244540641",
  appId: "1:901244540641:web:eab70638d2d17455e949a0",
};

const VAPID_KEY = "BBEpfbnhYpYFzUnproil5mnd4uQYB7aHvftyzEMvZXZy26KCFNtHcdI7cEB5xWRzWfHA6x-VbOprgmPfmZ9r6iE";

export async function registerForPush(): Promise<string | null> {
  try {
    if (!(await isSupported())) return null;
    if (typeof Notification === "undefined") return null;
    const perm = Notification.permission === "default" ? await Notification.requestPermission() : Notification.permission;
    if (perm !== "granted") return null;

    const app = getApps().length ? getApps()[0] : initializeApp(firebaseConfig);
    const reg = await navigator.serviceWorker.register("/firebase-messaging-sw.js");
    const messaging = getMessaging(app);
    return await getToken(messaging, { vapidKey: VAPID_KEY, serviceWorkerRegistration: reg });
  } catch {
    return null; // best-effort -- the app works fine without push
  }
}
