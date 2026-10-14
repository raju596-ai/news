# Step-by-Step Guide: How to Get `client_secret.json` for YouTube Uploads

This guide walks you through generating the **`client_secret.json`** file from the Google Cloud Console. This allows your news platform to upload and schedule videos directly to your YouTube channel.

---

### Step 1: Open Google Cloud Console
1. Open your browser and go to: **[Google Cloud Console](https://console.cloud.google.com/)**.
2. **Sign in** with the Google account that owns or manages your YouTube channel.

---

### Step 2: Create a New Project
1. At the top of the page, click the **project dropdown** (next to the "Google Cloud" logo).
2. Click **"NEW PROJECT"** in the top right of the modal.
3. Project Name: Enter **`YouTube News Uploader`** (or any name you prefer).
4. Click **"CREATE"**.
5. Wait ~5 seconds, then click the project dropdown again and **select your new project**.

---

### Step 3: Enable the YouTube Data API v3
1. In the left navigation menu (or the search bar at the top), go to **APIs & Services** -> **Library**.
2. In the search box, search for: **`YouTube Data API v3`**.
3. Click on **"YouTube Data API v3"** from the search results.
4. Click the blue **"ENABLE"** button.

---

### Step 4: Configure the OAuth Consent Screen
1. In the left menu under **APIs & Services**, click **OAuth consent screen** (or navigate to `APIs & Services` -> `OAuth consent screen`).
2. Under **User Type**, select **"External"**.
3. Click **"CREATE"**.
4. Fill in the required fields:
   - **App name**: `News Video Uploader`
   - **User support email**: Select your email address.
   - **Developer contact information**: Enter your email address.
5. Click **"SAVE AND CONTINUE"** at the bottom.
6. **Scopes Step**:
   - Click **"ADD OR REMOVE SCOPES"**.
   - In the filter search box, type `youtube.upload`.
   - Check the box for: `.../auth/youtube.upload` (Upload YouTube videos and manage your YouTube videos).
   - Click **"UPDATE"** at the bottom of the side panel.
   - Click **"SAVE AND CONTINUE"**.
7. **Test Users Step (IMPORTANT!)**:
   - Click **"+ ADD USERS"**.
   - Type the **exact Google email address** that manages your YouTube channel.
   - Click **"ADD"**.
   - *(This allows your account to upload without needing official Google app verification).*
   - Click **"SAVE AND CONTINUE"**.
8. Click **"BACK TO DASHBOARD"**.

---

### Step 5: Create the OAuth Client ID
1. In the left menu under **APIs & Services**, click **Credentials**.
2. Click **"+ CREATE CREDENTIALS"** at the top -> select **"OAuth client ID"**.
3. Under **Application type**, choose: **"Desktop app"** *(Do NOT choose Web Application)*.
4. **Name**: Enter `YouTube Desktop Client`.
5. Click **"CREATE"**.

---

### Step 6: Download the JSON File
1. A popup window will appear saying **"OAuth client created"**.
2. Click **"DOWNLOAD JSON"** (or click the ⬇️ download icon next to the client in the credentials table).
3. The downloaded file will have a long name like `client_secret_xxxxxxxx-xxxxxxxx.apps.googleusercontent.com.json`.

---

### Step 7: Place It in the Project
1. **Rename** the downloaded file to:
   ```
   client_secret.json
   ```
2. Move or copy this file into your project's data folder:
   ```
   D:\news\data\client_secret.json
   ```
3. Run the sync command (or it will sync automatically) so it also copies to `D:\news - Copy\data\client_secret.json`.

---

### What Happens on First Upload?
When you initiate an upload for the first time, your default browser opens a Google OAuth authorization page.

Because this is your own private developer app (in "Testing" mode), Google will show a standard safety prompt. Here is how to complete it:

#### If you see "Google hasn't verified this app":
1. Click the small link: **"Advanced"** (located on the bottom-left of the warning card).
2. Click **"Go to News Video Uploader (unsafe)"** (it is labeled "unsafe" only because it's a private script, not a public commercial app).
3. Check the box next to **"Upload YouTube videos"** (or "Manage your YouTube videos").
4. Click **"Continue"** / **"Allow"**.
5. The browser will display: *"The authentication flow has completed. You may close this window."*
6. Your credentials are now permanently saved to `data/token.json`. **All future uploads will happen 100% automatically in the background without any prompts!**

#### If you see "Access blocked: Error 403 access_denied":
This means the Gmail account you are signing in with hasn't been added to your test list yet:
1. Open [Google Cloud Console - OAuth Consent Screen](https://console.cloud.google.com/apis/credentials/consent).
2. Scroll to the **"Test users"** section.
3. Click **"+ ADD USERS"**.
4. Enter the **exact Gmail address** you are signing in with.
5. Click **"SAVE"** and retry uploading.

