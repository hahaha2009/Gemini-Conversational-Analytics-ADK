# Panduan Menjalankan Gemini CA ADK Agent

Dokumen ini adalah ringkasan cara menjalankan konfigurasi **Conversational Analytics (CA) Agent** di lingkungan *Cloudtop* Anda menggunakan 3 metode arsitektur yang tersedia di repositori ini.

---

## Prasyarat Utama: Otentikasi Google Cloud
Karena Anda mengalami `gcloud not found` di *Cloudtop*, kemungkinan *package*-nya belum ter-install secara global atau tidak ada di PATH Anda. Anda bisa meng-install-nya dengan instruksi standar Debian/Ubuntu:

```bash
# 1. Install gcloud CLI
sudo apt-get update
sudo apt-get install apt-transport-https ca-certificates gnupg curl
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list
sudo apt-get update && sudo apt-get install google-cloud-cli

# 2. Login ke Ekosistem Google Cloud (Sangat Penting!)
gcloud auth login
gcloud auth application-default login
```

> [!IMPORTANT]
> Langkah `gcloud auth application-default login` **wajib** dijalankan. Ini adalah penyebab utama error `ServiceUnavailable: 503 No service account scopes specified` pada skrip Python Anda sebelumnya!

---

## 1. Integrasi Gemini Enterprise > CA Agent (Production/UI)
Metode ini adalah alur deployment utuh. Data dari BigQuery diteruskan ke infrastruktur Google ADK (Reasoning Engine), lalu didaftarkan secara resmi ke tampilan interaktif Gemini Enterprise Workspace Anda.

**Langkah Instalasi:**
1. **Buat Metadata "Backend" Data Agent (Google Cloud CA API)**
   ```bash
   source .venv/bin/activate
   export $(cat .env | xargs)
   python scripts/admin_tools.py
   ```
2. **Deploy Kode Agen ke Vertex AI (Reasoning Engine)**
   ```bash
   bash scripts/deploy_agents.sh
   # CATAT: Anda akan mendapatkan string RESOURCE_NAME panjang di akhir proses ini
   ```
3. **Instal Resource Otentikasi** *(Menyiapkan portal OAuth)*
   ```bash
   python scripts/setup_auth.py
   ```
4. **Registrasi Agen ke Aplikasi Gemini Enterprise**
   ```bash
   # Ganti <RESOURCE_NAME> dengan output dari scripts/deploy_agents.sh di atas
   # CONTOH: projects/1029529.../locations/us-central1/reasoningEngines/7326...
   python scripts/register_agents.py --resource-name <RESOURCE_NAME>
   ```

> [!WARNING]
> **Mengatasi Error "FAILED_PRECONDITION: {id} is used by another agent"**
> Jika pada Langkah 4 pendaftaran gagal dengan alasan nama *Authorization* terkunci oleh agen lain yang usang, Anda harus merilis/(menghapus paksanya) langsung dari *backend* Vertex AI. Cukup jalankan *script cleaner* resmi yang sudah disiapkan:
> ```bash
> python scripts/unregister_agent.py
> ```
> Skrip di atas akan merontokkan semua ikatan agen *"zombie"* peninggalan Anda di *backend* beserta *Resources* otentikasinya. Setelah terhapus sempurna, Anda bebas mengulangi Langkah 3 (setup) lalu Langkah 4 (register) lagi tanpa masalah konflik!

Setelah sukses, Anda bisa membuka layanan Gemini Enterprise Workspace di browser, mencari Ekstensi "CBS Agent", dan langsung mulai *chatting*.

---

## 2. Integrasi test_web > CA Agent (Local Web Testing)
Metode ini mengizinkan Anda untuk mensimulasikan aliran login pengguna memakai jembatan OAuth *Identity Passthrough* secara lokal tanpa perlu menunggu perambinan dari UI produk Gemini Enterprise. Sangat bermanfaat untuk iterasi cepat.

**Langkah Instalasi:**
1. Pastikan Anda sudah sukses menjalankan skrip `deploy_agents.sh` dari Metode 1.
2. Salin *Resource Name* Engine yang Anda buat tadi ke dalam `REASONING_ENGINE_ID` di file `.env` (atau setara jika diperlukan).
3. **Jalankan Aplikasi Web Flask Lokal**:
   ```bash
   cd test_web
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   
   # Jalankan Web Server
   python app.py
   ```

> [!TIP]
> **Akses Aplikasi dari Luar Cloudtop**
> Jika Anda menguji di *Cloudtop* namun ingin mengakses UI dari laptop lokal Anda (memastikan *redirect URI localhost:8080* valid saat login OAuth), gunakan SSH *port forwarding* dari terminal lokal Anda:
> ```bash
> ssh -L 8080:localhost:8080 cloudtop-ynd-glinux.c.googlers.com
> ```
> Langkah ini vital agar Google menyetujui parameter `http://localhost:8080/auth/callback`.

4. Buka Browser (lokal) dan arahkan ke **http://localhost:8080**, klik "Login with Google". Anda akan melihat kotak input obrolan mandiri untuk mengetes Agen CBS.

---

## 3. Integrasi test_direct_ca.py (Backend CLI Testing)
Gunakan skrip `scripts/test_direct_ca.py` jika Anda **hanya** ingin memeriksa apakah perintah obrolan Anda membuahkan SQL Script BigQuery yang valid dan benar-benar menarik *Data Rows*. Skrip ini *memotong jalur* tanpa melewati ADK/Reasoning Engine sama sekali, melainkan langsung berinteraksi dari terminal ke Vertex AI CA API.

> [!TIP]
> Metode ini paling disarankan saat fase pertama *Debugging* jika BigQuery Dataset Anda gagal terbaca (bisa menolong memastikan masalah izin letaknya di BigQuery atau di Prompt/Kode ADK Anda).

**Langkah Pengujian:**
1. Pastikan Anda sudah menjalankan `python scripts/admin_tools.py` agar objek CA agent terdaftar di *backend* GCP.
2. Tembakkan promt lewat sintaks bawaannya langsung dari terminal utama:
   ```bash
   source .venv/bin/activate
   export $(cat .env | xargs)
   
   # Berikan pertanyaan yang relevan diapit dengan tanda kutip
   python scripts/test_direct_ca.py "How many customers do we have mapped to the Priority segment?"
   ```

Skrip di atas akan mengembalikan cetakan langsung (Print) di layar mengenai struktur percakapan, SQL Generator log, status eksekusi, serta limit barisan data (*Rows*) hasil tembusannya!
