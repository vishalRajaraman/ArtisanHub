# ArtisanHub (ArtConnect) 🎨✨

**Empowering Local Craftsmanship, Transforming Hidden Heritage into a Global Legacy.**

ArtisanHub is an AI-powered marketplace designed to bridge the gap between rural artisans and global buyers. It leverages Generative AI, Computer Vision, and Augmented Reality to help artisans appraise, list, and market their work without needing technical expertise, while offering buyers an immersive discovery experience.

---

## 🚀 Key Features

### For Artisans
* **🎙️ Voice-to-Listing (Sarvam AI):** Artisans can simply describe their art using their voice. The system transcribes and refines the description into professional marketing copy in English.
* **🤖 AI Appraisal & Valuation (Google Gemini):** Analyzes the artwork's image to determine:
    * **Art Style & Technique** (e.g., Madhubani, Oil on Canvas).
    * **Fair Market Price** (Conservative low/high estimates in INR).
    * **App Title & Caption:** Generates emotional titles and Instagram-ready captions.
* **📱 Automated Social Marketing:** Automatically posts the artwork to a connected Instagram account with trending hashtags upon publishing.

### For Buyers
* **🔍 Semantic Discovery:** Search by "vibe" or emotion (e.g., *"peaceful sunset in a village"*) using Vector Search (Pinecone).
* **👓 Augmented Reality (AR) View:** A built-in WebAR viewer allows buyers to project the painting onto their own wall to see how it fits before purchasing.
* **🛒 Direct & Secure:** Direct connection with SMS notifications via Twilio for order updates.

---

## 🛠️ Tech Stack

* **Backend:** Python (FastAPI)
* **Database:** SQLite / PostgreSQL (via SQLAlchemy)
* **Vector Search:** Pinecone (Serverless)
* **AI Models:**
    * **Vision & Text:** Google Gemini 1.5/2.5 Flash
    * **Speech-to-Text:** Sarvam AI (`saaras:v2.5`)
    * **Embeddings:** Google `text-embedding-004`
* **Integrations:** Twilio (SMS), Instagrapi (Instagram Automation)
* **Frontend:** HTML5, Tailwind CSS, Vanilla JS

---

## 🔧 Installation & Setup

1.  **Clone the Repository**
    ```bash
    git clone [https://github.com/yourusername/artisanhub.git](https://github.com/yourusername/artisanhub.git)
    cd artisanhub
    ```

2.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure Environment Variables**
    Create a `.env` file in the root directory and add your keys:
    ```env
    # AI & Vector DB
    GOOGLE_API_KEY=your_gemini_api_key
    PINECONE_API_KEY=your_pinecone_api_key
    SARVAM_API_KEY=your_sarvam_api_key

    # Database
    DATABASE_URL=sqlite:///./artconnect.db

    # Security
    SECRET_KEY=your_super_secret_key

    # Twilio (SMS)
    TWILIO_SID=your_twilio_sid
    TWILIO_TOKEN=your_twilio_auth_token
    TWILIO_PHONE=your_twilio_phone_number

    # Instagram (Automation)
    IG_USERNAME=your_instagram_username
    IG_PASSWORD=your_instagram_password
    ```

4.  **Run the Application**
    ```bash
    uvicorn main:app --reload
    ```

5.  **Access the App**
    Open `http://127.0.0.1:8000` in your browser.

---

## 📂 Project Structure

* `main.py`: Core application logic (API endpoints, AI integration).
* `database.py`: Database models and connection setup.
* `static/`: Frontend files (HTML, CSS, JS) including the AR viewer.
* `requirements.txt`: Python dependencies.

---

## 🔮 Future Roadmap

* **Multilingual Support:** Translate the UI into local Indic languages.
* **Blockchain Integration:** Mint heritage art as NFTs for provenance.
* **Logistics API:** Automate shipping label generation.

---

**License:** MIT
