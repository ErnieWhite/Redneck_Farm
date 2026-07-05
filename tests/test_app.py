import threading
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

        with self.assertRaisesRegex(ValueError, "player names"):
            game.join_player("   ")

    def test_name_validation_edge_cases(self) -> None:
        game = FarmGame()

        snapshot = game.join_player("A" * 24)
        self.assertEqual(snapshot["players"][0]["name"], "A" * 24)

        with self.assertRaisesRegex(ValueError, "player names"):
            game.join_player("-Farmer")

    def test_crop_must_be_allowed(self) -> None:
        game = FarmGame(plot_count=1)
        game.join_player("Farmer2")

        with self.assertRaisesRegex(ValueError, "listed crops"):
            game.apply_action("Farmer2", "plant", 0, "Beans")

    def test_only_one_player_can_claim_an_empty_plot(self) -> None:
        game = FarmGame(plot_count=1)
        game.join_player("Farmer1")
        game.join_player("Farmer2")
        barrier = threading.Barrier(2)
        results: list[str] = []

        def plant(player: str) -> None:
            barrier.wait()
            try:
                game.apply_action(player, "plant", 0, "Corn")
                results.append(f"{player}:planted")
            except ValueError:
                results.append(f"{player}:blocked")

        first = threading.Thread(target=plant, args=("Farmer1",))
        second = threading.Thread(target=plant, args=("Farmer2",))
        first.start()
        second.start()
        first.join()
        second.join()

        planted = [result for result in results if result.endswith("planted")]
        blocked = [result for result in results if result.endswith("blocked")]

        self.assertEqual(len(planted), 1)
        self.assertEqual(len(blocked), 1)
        self.assertEqual(game.snapshot()["plots"][0]["crop"], "Corn")


if __name__ == "__main__":
    unittest.main()
