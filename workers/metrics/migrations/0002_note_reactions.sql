CREATE TABLE IF NOT EXISTS note_reaction_totals (
  slug TEXT PRIMARY KEY,
  likes INTEGER NOT NULL CHECK (likes >= 0)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS note_reactions (
  slug TEXT NOT NULL,
  visitor TEXT NOT NULL,
  PRIMARY KEY (slug, visitor)
) WITHOUT ROWID;

CREATE TRIGGER IF NOT EXISTS note_reactions_add AFTER INSERT ON note_reactions
BEGIN
  INSERT INTO note_reaction_totals (slug, likes) VALUES (NEW.slug, 1)
  ON CONFLICT(slug) DO UPDATE SET likes = likes + 1;
END;

CREATE TRIGGER IF NOT EXISTS note_reactions_remove AFTER DELETE ON note_reactions
BEGIN
  UPDATE note_reaction_totals SET likes = likes - 1 WHERE slug = OLD.slug;
END;
