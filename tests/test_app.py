import unittest

from app import FarmGame


class FarmGameTests(unittest.TestCase):
    def test_join_plant_water_and_harvest_cycle(self) -> None:
        game = FarmGame(plot_count=1)

        game.join_player("Farmer1")
        game.apply_action("Farmer1", "plant", 0, "Corn")
        game.apply_action("Farmer1", "water", 0)
        snapshot = game.apply_action("Farmer1", "water", 0)

        self.assertEqual(snapshot["plots"][0]["status"], "Ready to harvest")

        snapshot = game.apply_action("Farmer1", "harvest", 0)

        self.assertEqual(snapshot["plots"][0]["crop"], None)
        self.assertEqual(snapshot["players"][0]["harvests"], 1)

    def test_invalid_name_is_rejected(self) -> None:
        game = FarmGame()

        with self.assertRaisesRegex(ValueError, "player names"):
            game.join_player("!!!!")

    def test_crop_must_be_allowed(self) -> None:
        game = FarmGame(plot_count=1)
        game.join_player("Farmer2")

        with self.assertRaisesRegex(ValueError, "listed crops"):
            game.apply_action("Farmer2", "plant", 0, "Beans")


if __name__ == "__main__":
    unittest.main()
