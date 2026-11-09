# Access the demo over an HTTPS tunnel

A tunnel forwards a public HTTPS URL to the backend running on your computer. Use it to open the demo on a phone, where browser geolocation and Google Sign-In require HTTPS. A tunnel does not deploy the application to a permanent server.

## 1. Start the backend

From the project root, start the backend on port `8000` using the [README instructions](../README.md#run-on-windows). Verify the app locally first:

- <http://localhost:8000/api/health>
- <http://localhost:8000/app/>

Create one tunnel and point it to `localhost:8000`. Do not run multiple tunnels for the same domain or forward that domain to different ports.

## 2. Start ngrok

Install ngrok from the [official download page](https://ngrok.com/download) and configure your authtoken using the [ngrok setup guide](https://ngrok.com/docs/getting-started/). Open a second terminal and run:

```powershell
ngrok http 8000
```

Open the HTTPS address shown on the `Forwarding` line, then append `/app/` to go directly to the app. Each ngrok Free account receives an automatically assigned dev domain. `ngrok http 8000` uses that domain, so the URL stays the same when you restart the ngrok agent. Free accounts use their assigned domain; choosing a different domain depends on the plan. See the [ngrok domains documentation](https://ngrok.com/docs/gateway/domains) for current limits.

Keep both the backend and ngrok terminals running during the demo. Open `http://localhost:4040` to inspect forwarded requests and responses.

## 3. Allow Google Sign-In on the tunnel

1. Open [Google Cloud Console](https://console.cloud.google.com/) and select the project containing your OAuth client.
2. Go to Google Auth Platform → Clients and select the **Web application** client.
3. Add the tunnel's HTTPS origin under **Authorized JavaScript origins**, for example `https://your-domain.ngrok-free.dev`. Do not include `/app/login.html`, a query string, or a trailing slash.
4. Confirm `GOOGLE_CLIENT_ID` in `.env` matches this client, then restart the backend.
5. If the tunnel domain changes, add the new origin to the same OAuth client and reload the sign-in page.

The current sign-in page uses the Google Identity Services popup and sends the ID token to the backend for verification. This flow does not require an **Authorized redirect URI**. See Google's guide to [getting a Google API client ID](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid).

## 4. Check on your phone

1. Open the tunnel's HTTPS URL followed by `/app/`.
2. Allow location access when prompted and make sure Location/GPS is enabled on the phone.
3. Confirm the phone has Internet access. Maps and address search use external services, which may be blocked or unavailable on some networks.
4. If the app does not load, verify the backend is still running and ngrok forwards to port `8000`, then open `/api/health` through the public domain.

Do not share or commit `.env`, ngrok authtokens, OAuth client secrets, JWT secrets, payment keys, or payment account details. A public tunnel exposes your development machine to Internet traffic; use demo data and stop ngrok after the presentation.
