from __future__ import annotations

import unittest

from PIL import Image

from sprite_sheet_cleaner.app.models.project_document import ProjectDocument
from sprite_sheet_cleaner.app.services.source_repository import SourceRepository


class SourceRepositoryTests(unittest.TestCase):
    def test_candidate_requires_explicit_activation(self) -> None:
        repository = SourceRepository()
        original = Image.new("RGBA", (4, 4), (255, 0, 255, 255))
        repository.open_original(original, "source.png")

        candidate = repository.create_candidate(
            Image.new("RGBA", (4, 4), (0, 0, 0, 0)),
            engine_id="exact_key",
            settings={"tolerance": 30},
        )

        self.assertIsNone(repository.document.active_revision)
        self.assertEqual(repository.document.candidate_revision_id, candidate.revision_id)
        self.assertEqual(repository.active_image().getpixel((0, 0)), (255, 0, 255, 255))

        active = repository.activate_candidate()

        self.assertEqual(active.revision_id, repository.document.active_revision_id)
        self.assertIsNone(repository.document.candidate_revision_id)
        self.assertEqual(repository.active_image().getpixel((0, 0)), (0, 0, 0, 0))

    def test_replacing_candidate_does_not_change_active_revision(self) -> None:
        repository = SourceRepository(ProjectDocument())
        repository.open_original(Image.new("RGBA", (2, 2), "white"))
        first = repository.create_candidate(
            Image.new("RGBA", (2, 2), "red"), engine_id="exact_key", settings={}
        )
        repository.activate_candidate()

        second = repository.create_candidate(
            Image.new("RGBA", (2, 2), "blue"), engine_id="exact_key", settings={}
        )

        self.assertEqual(repository.document.active_revision_id, first.revision_id)
        self.assertEqual(repository.document.candidate_revision_id, second.revision_id)
        self.assertEqual(repository.active_image().getpixel((0, 0)), (255, 0, 0, 255))


if __name__ == "__main__":
    unittest.main()
