import 'models.dart';

/// Ce que les écrans lisent. Une seule source : le serveur Nexis.
///
/// Aujourd'hui seule l'implémentation de démonstration existe (aperçu
/// avec données fictives). La connexion au serveur (/api/app/v1, appareils
/// et sessions déjà en place côté backend) viendra la remplacer sans
/// changer les écrans.
abstract class NexisRepository {
  Future<Profile> profile();
  Future<Wallet> wallet();
  Future<List<Mission>> missions();
  Future<List<Movement>> movements();

  Future<Mission> mission(int id);

  /// Les devis reçus pour une mission, le mieux noté en premier.
  Future<List<Quote>> quotes(int missionId);

  Future<List<PayAccount>> payAccounts();

  /// Demande le paiement du devis choisi à l'opérateur. Le montant est
  /// celui du devis enregistré sur le serveur, jamais un calcul de l'app.
  Future<Mission> pay(int missionId, int quoteId, MobileOperator operator);

  /// Le client confirme que le travail est fait : le serveur verse
  /// l'argent sécurisé au prestataire.
  Future<Mission> confirmDone(int missionId);
}
