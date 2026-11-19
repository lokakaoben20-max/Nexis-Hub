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
}
