"""Abonnementen: plannen en add-ons, rechten over tijd, en Stripe.

- ``catalog``: plannen, add-ons, prijzen in centen en de rechten die ze geven;
- ``subscriptions``: wanneer een betaald abonnement nog rechten geeft;
- ``stripe``: webhook-handtekeningen controleren en de Stripe-API aanroepen
  (vereist de extra ``billing``, dus requests).

De app bewaart zelf welke gebruiker welk abonnement heeft; dit pakket weet
niets van gebruikers of databases.
"""
