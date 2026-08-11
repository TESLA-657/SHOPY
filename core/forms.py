from django import forms
from .models import Vendeur,Produit,Categorie
from django.contrib.auth.models import User
import re

class InscriptionVendeurForm(forms.Form):
    nom_boutique = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex: AB STORE'
        })
    )
    numero = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+224 6XX XX XX XX'
        })
    )
    ville = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex: Conakry'
        })
    )
    mot_de_passe = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Choisissez un mot de passe'
        })
    )
    confirmer_mot_de_passe = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirmez le mot de passe'
        })
    )

    def clean_numero(self):
        numero = self.cleaned_data.get('numero')
        # Enlever les espaces et +
        numero_clean = re.sub(r'[\s\+]', '', numero)
        #doit contenir que des chiffres
        if not numero_clean.isdigit():
            raise forms.ValidationError("Numéro invalide.")
        # doit avoir 8 ou 9 chiffres
        if len(numero_clean) < 8:
            raise forms.ValidationError("Numéro trop court.")
        return numero
        
    def clean_nom_boutique(self):
        nom = self.cleaned_data.get('nom_boutique')
        # Pas de caractères spéciaux dangereux
        if re.search(r'[<>"\';]', nom):
            raise forms.ValidationError("Caractères spéciaux non autorisés.")
        return nom

    def clean(self):
        cleaned_data = super().clean()
        mdp = cleaned_data.get('mot_de_passe')
        confirm = cleaned_data.get('confirmer_mot_de_passe')
        nom_boutique = cleaned_data.get('nom_boutique')

        if mdp and confirm and mdp != confirm:
            raise forms.ValidationError("Les mots de passe ne correspondent pas.")

        # Validation force du mot de passe
        if mdp:
            if len(mdp) < 8:
                raise forms.ValidationError("Le mot de passe doit contenir au moins 8 caractères.")
            if not re.search(r'[A-Za-z]', mdp):
                raise forms.ValidationError("Le mot de passe doit contenir au moins une lettre.")
            if not re.search(r'\d', mdp):
                raise forms.ValidationError("Le mot de passe doit contenir au moins un chiffre.")

        if nom_boutique and User.objects.filter(username=nom_boutique).exists():
            raise forms.ValidationError("Ce nom de boutique est déjà utilisé.")

        return cleaned_data
    
class ProduitForm(forms.ModelForm):
    categorie = forms.ModelChoiceField(
        queryset=Categorie.objects.all(),
        empty_label="-- Choisir une catégorie --",
        required=True,
    )

    class Meta:
        model = Produit
        fields = [
            'nom', 'photo', 'prix', 'quantite',
            'description', 'categorie',
            'promo', 'prix_promo', 'jours_promo'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Photo optionnelle si déjà choisie via galerie
        self.fields['photo'].required = False
        self.fields['prix_promo'].required = False
        self.fields['jours_promo'].required = False
        self.fields['description'].required = False
        