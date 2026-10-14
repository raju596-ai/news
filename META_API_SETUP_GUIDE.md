# Meta (Facebook & Instagram) Video Upload Setup Guide

This guide walks you through setting up automated video publishing to your **Facebook Page** and **Instagram Professional/Creator Account**.

---

## Architecture Overview

```
                      ┌──────────────────────────────────────┐
                      │    AI Generated News Video (1080p)   │
                      │  • final_news_video.mp4              │
                      │  • thumbnail.jpg                     │
                      │  • metadata.txt                      │
                      └──────────────────┬───────────────────┘
                                         │
                    ┌────────────────────┴────────────────────┐
                    ▼                                         ▼
         ┌─────────────────────┐                   ┌─────────────────────┐
         │   FACEBOOK UPLOADER │                   │  INSTAGRAM UPLOADER │
         │ • Resumable upload  │                   │ • Resumable container│
         │ • Full 16:9 1080p   │                   │ • Reels/Feed video  │
         │ • Title & desc      │                   │ • Auto-published    │
         │ • Custom thumbnail  │                   │ • Custom cover      │
         └─────────────────────┘                   └─────────────────────┘
```

---

## Requirements

1. A **Facebook Page** (e.g. your news channel page).
2. An **Instagram Account** switched to **Professional / Creator** (in Instagram app: *Settings -> Account -> Switch to professional account*).
3. Connect your Instagram account to your Facebook Page:
   - On Facebook: Go to your Page -> *Settings -> Linked Accounts -> Instagram -> Connect Account*.

---

## Step 1: Create a Free Meta Developer App

1. Go to [developers.facebook.com](https://developers.facebook.com/) and log in with your Facebook account.
2. Click **My Apps** in the top-right corner, then click **Create App**.
3. Choose **Other** -> Click **Next**.
4. Select App Type: **Business** -> Click **Next**.
5. Enter an App Name (e.g. `News Channel Automation`) and your contact email -> Click **Create app**.

---

## Step 2: Add Products (Pages API & Instagram Graph API)

1. In your App Dashboard, find **Add products to your app**.
2. Find **Instagram Graph API** and click **Set Up**.
3. Find **Facebook Login for Business** or **Pages** and click **Set Up**.

---

## Step 3: Generate a Long-Lived Access Token

1. Go to the [Meta Graph API Explorer](https://developers.facebook.com/tools/explorer/).
2. In the top-right:
   - **Meta App**: Select your newly created app.
   - **User or Page**: Select your **Facebook Page**.
3. Under **Permissions**, add:
   - `pages_show_list`
   - `pages_read_engagement`
   - `pages_manage_posts`
   - `publish_video`
   - `instagram_basic`
   - `instagram_content_publish`
4. Click **Generate Access Token** and approve the Facebook permissions popup.
5. *(Optional but Recommended)*: Convert this token into a **Never-Expiring Long-Lived Token**:
   - Go to [Access Token Debugger](https://developers.facebook.com/tools/debug/accesstoken/).
   - Paste your token and click **Debug**.
   - Click **Extend Access Token** at the bottom to get a 60-day / permanent token.

---

## Step 4: Find Your IDs

### A. Facebook Page ID:
- In Graph API Explorer, query:
  `GET me?fields=id,name`
- The `id` returned is your `page_id`.

### B. Instagram Account ID:
- In Graph API Explorer, query:
  `GET {page_id}?fields=instagram_business_account`
- The `id` under `instagram_business_account` is your `account_id`.

---

## Step 5: Save Credentials in the Application

Copy `data/meta_credentials.template.json` to `data/meta_credentials.json`:

```json
{
  "facebook": {
    "page_id": "123456789012345",
    "page_access_token": "EAA..."
  },
  "instagram": {
    "account_id": "17841400000000000",
    "access_token": "EAA..."
  }
}
```

*Alternatively*, you can set them in your `.env` file:
```env
FB_PAGE_ID=123456789012345
FB_PAGE_ACCESS_TOKEN=EAA...
IG_ACCOUNT_ID=17841400000000000
IG_ACCESS_TOKEN=EAA...
```

---

## Step 6: Test Direct Upload

1. Open your browser to the News Dashboard: `http://localhost:8000/`.
2. Once a story video is generated:
   - Click **👥 Upload Facebook** to publish natively to your Facebook Page.
   - Click **📸 Upload Instagram** to publish directly to Instagram.
3. Track upload progress in real-time right on the dashboard.
