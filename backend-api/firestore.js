
import admin from "firebase-admin";
import fs from "fs";

const serviceAccount = JSON.parse(fs.readFileSync("./serviceAccount.json", "utf8"));

admin.initializeApp({
  credential: admin.credential.cert(serviceAccount)
});

const db = admin.firestore();

export const firestore = {
  async getVerseById(id) {
    try {
      let collectionName = 'scripture_verses'; 
      if (id.startsWith('quran_')) {
        collectionName = 'quran_verses'; 
      }

      const docRef = db.collection(collectionName).doc(id);
      const doc = await docRef.get();
      
      if (!doc.exists) {
        console.warn(`Verse with ID "${id}" not found in Firestore collection "${collectionName}".`);
        return null;
      }
      return doc.data();
    } catch (err) {
      console.error(`Error fetching verse ${id}:`, err);
      return null;
    }
  }
};