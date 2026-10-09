# The Go To — Daily Curated News (PWA)

"The Go To" is a personalized Progressive Web App (PWA) newspaper delivering daily news across:
- **Local News & Events**: Kenner, Metairie, and New Orleans, LA
- **Tech**: Breakthroughs in computing, AI, and chips
- **Aviation**: Commercial flight, airlines, and aerospace
- **Drones**: Commercial delivery, FAA regulations, and emergency UAVs
- **Cars**: Automotive technology, solid-state batteries, and electric vehicles
- **Presidential Direct Actions**: Official White House Executive Orders only (zero partisan punditry)
- **Strict Guardrails**: 100% Sports-Free & Partisan-Free

---

## How to Deploy in 2 Minutes (Free on GitHub Pages)

1. Create a new repository on [GitHub](https://github.com/new) named `the-go-to`.
2. Upload all the files from this folder (`index.html`, `manifest.json`, `sw.js`, `stories.json`, `icon-192.png`, `icon-512.png`, `update_news.py`, and the `.github` folder).
3. In your GitHub repository:
   - Go to **Settings** > **Pages**.
   - Under **Build and deployment** > **Branch**, select `main` (or `master`) and folder `/ (root)`.
   - Click **Save**.
4. GitHub will give you a live URL (e.g. `https://yourusername.github.io/the-go-to/`).

---

## How to Install as an App Icon ("Add to Home Screen")

Once you open your live URL:

### On iPhone / iPad (Safari)
1. Open the URL in **Safari**.
2. Tap the **Share** button (the square with an arrow pointing up).
3. Scroll down and tap **Add to Home Screen**.
4. Tap **Add**. "The Go To" will now appear on your home screen with its custom app icon and launch in full-screen standalone mode without any browser address bar!

### On Android (Chrome)
1. Open the URL in **Chrome**.
2. Tap the **Install App** banner at the top, or open the three-dot menu and select **Install app** / **Add to Home screen**.
3. It will install directly into your app drawer and home screen.

### On Mac / Windows / Chromebook (Chrome / Edge)
1. In the address bar, click the **Install** icon (a screen with a down arrow).
2. "The Go To" runs in its own dedicated, clean window.

---

## Automated Daily Updates

The included `.github/workflows/daily_update.yml` runs automatically every morning at **6:00 AM Central Time (11:00 UTC)**. It executes `update_news.py`, updates `stories.json`, and commits the changes back to your repository. Because `sw.js` uses a network-first strategy for `stories.json`, your installed PWA will automatically show the latest edition whenever you open the app!
