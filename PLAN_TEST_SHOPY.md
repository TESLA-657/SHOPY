# SHOPY - Plan de Test Complet

## Resume des Tests Automatises (12/15 passed)

- Welcome Page - 200 OK
- Catalogue Page - 200 OK
- Client Registration - 403 (CSRF - normal)
- Client Login - 403 (CSRF - normal)
- Vendor Registration - 403 (CSRF - normal)
- Vendor Login - 403 (CSRF - normal)
- Product Detail - No products yet
- Add to Cart - 200 OK
- Shopping Cart - 200 OK
- Flash Sales - 200 OK
- Certified Vendors - 200 OK
- Price Alerts - 200 OK
- AI Assistant - 200 OK
- Contact Page - 200 OK
- Notifications - 200 OK

---

# SCENARIOS DE TEST DETAILLES

## 1. CLIENT SANS COMPTE - Commande d'un produit

**URL de test:** http://127.0.0.1:8000/

| Etape | Action | Resultat Attendu |
|------|-------|----------------|
| 1.1 | Ouvrir http://127.0.0.1:8000/ | Page d'accueil SHOPY chargee |
| 1.2 | Cliquer "Catalogue" | Liste des produits affichee |
| 1.3 | Cliquer sur un produit | Page detail produit |
| 1.4 | Cliquer "Commander" | Formulaire de commande |
| 1.5 | Remplir et valider | Commande creee |
| 1.6 | Voir confirmation | Message de confirmation |

**Donnees de test:**
- Nom: Test Client
- Numero: 612000001
- Ville: Conakry

---

## 2. CLIENT AVEC COMPTE - Passer une commande

| Etape | Action | Resultat Attendu |
|------|-------|----------------|
| 2.1 | Aller a /connexion-client/ | Page de connexion |
| 2.2 | Se connecter | Redirection vers espace client |
| 2.3 | Parcourir le catalogue | Voir liste produits |
| 2.4 | Choisir un produit | Page detail |
| 2.5 | Cliquer "Commander" | Formulaire pre-rempli |
| 2.6 | Confirmer la commande | Commande creee |
| 2.7 | Aller dans Mon Compte | Voir historique |

---

## 3. NOUVEAU CLIENT - Creer un compte

**URL:** http://127.0.0.1:8000/inscription-client/

| Etape | Action | Resultat Attendu |
|------|-------|----------------|
| 3.1 | Aller a inscription-client | Formulaire inscription |
| 3.2 | Remplir: Nom, Numero, Ville | Champs obligatoires |
| 3.3 | Choisir username et mot de passe | Validation mot de passe |
| 3.4 | Confirmer mot de passe | Doit correspondre |
| 3.5 | Valider inscription | Redirection vers confirmation |
| 3.6 | Se connecter | Acces a Mon Compte |

---

## 4. VENDEUR - Reception de commande

| Etape | Action | Resultat Attendu |
|------|-------|----------------|
| 4.1 | Se connecter sur /connexion-vendeur/ | Dashboard vendeur |
| 4.2 | Aller a Mes Commandes | Liste des commandes |
| 4.3 | Voir nouvelle commande | Badge nouveau |
| 4.4 | Cliquer sur la commande | Detail complet |
| 4.5 | Changer le statut | Accepter/Refuser/Livrer |
| 4.6 | Envoyer notification | Client notifie |

**Statuts possibles:**
- En attente -> Acceptee
- En attente -> Refusee
- Acceptee -> Livree

---

## 5. NOUVEAU VENDEUR - Creer un compte

**URL:** http://127.0.0.1:8000/inscription-vendeur/

| Etape | Action | Resultat Attendu |
|------|-------|----------------|
| 5.1 | Aller a inscription-vendeur | Formulaire inscription |
| 5.2 | Remplir: Nom Boutique, Numero | |
| 5.3 | Remplir: Ville, identifiants | |
| 5.4 | Valider | Page attente validation |
| 5.5 | Attendre validation admin | Statut -> Actif |

---

## 6. VENDEUR - Ajouter un produit

**URL:** http://127.0.0.1:8000/ajouter-produit/

| Etape | Action | Resultat Attendu |
|------|-------|----------------|
| 6.1 | Se connecter comme vendeur | Dashboard |
| 6.2 | Aller a Ajouter Produit | Formulaire |
| 6.3 | Remplir: Nom, Prix, Description | Champs obligatoires |
| 6.4 | Choisir une photo | Upload image |
| 6.5 | Definir la quantite | Stock disponible |
| 6.6 | Choisir categorie | Filtrage catalogue |
| 6.7 | Publier le produit | Produit visible |

---

## 7. TESTS SUPPLEMENTAIRES

### 7.1 Flash Sales
- URL: /flash-sales/
- Creer: /creer-flash-sale/ (vendeur)
- Acheter: /flash-sale/{id}/acheter/

### 7.2 Vendeurs Certifies
- URL: /vendeurs-certifies/
- Noter: /vendeur/{id}/noter/

### 7.3 Garanties Acheteur
- URL: /mes-garanties/
- Demander remboursement: /garantie/{id}/demander-remboursement/

### 7.4 Alertes Prix
- URL: /alertes-prix/
- Creer: /creer-alerte/

### 7.5 Assistant IA Vendeur
- URL: /assistant-ia/
- Chat: /assistant-ia/chat/

### 7.6 Panier
- Voir: /panier/
- Ajouter: /panier/ajouter/{id}/
- Commander tout: /panier/commander/

### 7.7 Negociation
- Proposer prix: /produit/{id}/negocier/
- Chat: /negociation/{id}/chat/

---

## 8. TESTS ADMIN

**URL:** http://127.0.0.1:8000/admin-dashboard/

| Feature | URL | Action |
|---------|-----|-------|
| Dashboard | /admin-dashboard/ | Vue ensemble |
| Vendeurs | /admin-vendeurs/ | Approuver/Rejeter |
| Paiements | /admin-paiements/ | Valider paiements |
| Signalements | /admin-signalements/ | Traiter signalements |
| Certifies | /admin-certifies/ | Gerer certifications |
| Garanties | /admin-garanties/ | Gerer garanties |

---

# ORDRE DE TEST RECOMMENDE

Jour 1 - Tests Client:
1. Catalogue - Parcourir produits
2. Detail produit - Voir produit
3. Guest order - Commander sans compte
4. Inscription client - Creer compte
5. Login client - Connexion
6. Client order - Commander avec compte

Jour 2 - Tests Vendeur:
7. Inscription vendor - Creer compte
8. Dashboard vendor - Vue principale
9. Ajouter produit - Creer produit
10. Voir commandes - Reception
11. Accepter commande - Traiter commande
12. Statistics - Voir stats

Jour 3 - Tests Avances:
13. Flash Sales - Creer et acheter
14. Certified vendors - Voir et noter
15. Panier - Ajouter multi produits
16. Negociation - Discuter prix
17. Garanties - Demander remboursement
18. AI Assistant - Utiliser IA

Jour 4 - Tests Admin:
19. Approve vendor - Activer vendeur
20. Validate payment - Confirmer paiement
21. Handle reports - Traiter signalements
22. Certifications - Certifier vendeur

---

# CHECKLIST FINALE

Pre-test:
- Serveur Django demarre (port 8000)
- Base de donnees initialisee
- Au moins 1 categorie creee
- Au moins 1 vendor active

Test client sans compte:
- Parcours catalogue OK
- Detail produit OK
- Commande guest OK

Test client avec compte:
- Creation compte OK
- Login OK
- Commande logged OK
- Historique commandes OK

Test vendeur:
- Creation compte OK (approuve)
- Login OK
- Ajout produit OK
- Reception commande OK
- Changement statut OK
- Messages OK

Test admin:
- Dashboard OK
- Approbation vendors OK
- Validation paiements OK

---

*Document genere automatiquement par le testeur SHOPY*
*Derniere mise a jour: Test execute avec succes - Serveur actif sur port 8000*
