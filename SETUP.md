# Setup — no coding required

Every step below is a click or a copy-paste in your browser. Budget 20 minutes.
Everything here is free.

---

## 1. Make a GitHub account

Go to [github.com/signup](https://github.com/signup). GitHub is where your tracker
will live and run — think of it as a free computer that wakes up twice a day,
checks prices, and goes back to sleep.

## 2. Create the repository

Click the **+** in the top right → **New repository**.

- Name: `price-watch`
- **Public** — this matters. The free dashboard hosting only works on public
  repositories. Nothing private goes in here; it's product links and prices.
- Tick **Add a README file**
- Click **Create repository**

## 3. Upload the files

On your new repository page: **Add file** → **Upload files**.

Drag in everything from the folder I gave you:

```
index.html          the dashboard
tracker.py          the price checker
products.json       what you're tracking  ← the only file you'll edit often
data/               where prices get stored
.github/            the schedules and the add-item robot
```

> If dragging the folders doesn't preserve `data/` and `.github/`, upload the
> loose files first, then use **Add file → Create new file** and type
> `.github/workflows/track.yml` as the filename — GitHub creates the folders
> from the slashes. Paste the contents in.

Scroll down, click **Commit changes**.

## 4. Turn on the scheduler

Click the **Actions** tab. GitHub will ask you to confirm workflows —
click **I understand my workflows, go ahead and enable them**.

## 5. Turn on the dashboard

**Settings** → **Pages** (left sidebar) → under *Branch* pick **main** and **/ (root)**
→ **Save**.

After a minute your dashboard is live at:

```
https://YOUR-USERNAME.github.io/price-watch/
```

Bookmark it on your phone.

## 6. Already loaded: the MacBook Air

Your dashboard ships tracking the **MacBook Air 13" M5, 8-core GPU, 16GB, 512GB**
across Apple, Best Buy, Staples, Amazon.ca and Costco. Target is set to $1,299 —
change it in `products.json` whenever you like.

Apple's list price is $1,499 CAD, so $1,299 means you're waiting for roughly 13% off.

## 7. Run it once by hand

**Actions** tab → **Check prices** (left) → **Run workflow** → **Run workflow**.

Watch it go green, then open your dashboard. Prices should be there.

---

# Tracking more things

Open your dashboard and click **Track something new** at the bottom.

1. Type what it is
2. Optionally, the price that would make you buy
3. Open each store's product page in your browser, copy the address bar, paste
   them in — one per line

As you paste, it names each store and flags which ones you'll be entering by hand.
Press **Add it**, then **Create** on the GitHub page that opens. Two minutes later
it's on your dashboard with its first prices.

You never touch `products.json` for this. It works from your phone.

> Adding an item you're already tracking updates it rather than duplicating it —
> that's how you add a store to something later, or change a target price.

## A note on colours

Retailers give each colour its own product page. Midnight, Starlight, Silver and
Sky Blue are four different links even at the same price. The MacBook Air above
tracks Midnight where a colour had to be chosen.

If you don't care about colour, add the other colours' links as extra sources —
the tracker will surface whichever is cheapest. If you do care, leave it as is.

---

## Adding a price by hand

For Costco and Walmart, you look up the price and type it in — takes about ten seconds.

Open `data/manual-prices.csv`, click the pencil, add a line:

```
date,product_id,retailer,price,note
2026-08-30,sony-xm5,Costco Canada,329.99,warehouse tag
```

The `retailer` name must match `products.json` exactly. The tracker uses your most
recent line, so old entries can stay — they become your price history for that store.

## How alerts reach you

When a price drops, the tracker opens an **Issue** on your repository, and GitHub
emails you about it. Nothing to configure.

To also get phone push notifications, install the GitHub mobile app and sign in.

Close the issue once you've looked — a new one opens on the next drop.

## Changing how often it checks

In `.github/workflows/track.yml`, this line controls the schedule:

```yaml
- cron: "0 12,0 * * *"
```

Times are UTC. `12` and `0` mean 8am and 8pm Eastern. Four times a day would be
`"0 3,9,15,21 * * *"`. Twice a day is plenty for retail pricing — stores rarely
change prices more often, and it keeps you well inside the free tier.

---

## When something breaks

**A store shows "price not found on page"** — that store changed its website layout,
or it's blocking us. Switch that store to `"method": "manual"` and you'll still have
its history. Tell me which store and I'll write a proper reader for it.

**The dashboard is blank** — the tracker hasn't run yet, or Pages is still building.
Give it five minutes, then hard-refresh.

**The schedule stopped** — GitHub pauses scheduled jobs on repositories that sit
untouched for 60 days. Press **Run workflow** once and it resumes.

**Everything says "flat"** — that's just the first run. There's nothing to compare
against until the second check.

---

## What this deliberately doesn't do

It doesn't try to defeat Costco's or Walmart's bot protection. That's a losing arms
race, it violates their terms of use, and it would break constantly — which is exactly
what you ranked lowest. Ten seconds of typing gets you the same number, permanently.
