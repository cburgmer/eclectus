CREATE TABLE SimilarCharacters (
  GroupIndex INTEGER NOT NULL,              -- Similar character group index
  ChineseCharacter CHAR(1) NOT NULL,        -- Character
  PRIMARY KEY (GroupIndex, ChineseCharacter)
);