import numpy as np
from dwim.rag.embed import embed_texts

def test_embeddings_shape_and_normalized():
    E = embed_texts(["revert a git commit", "undo the last commit", "bake bread"])
    assert E.shape == (3, 384)
    assert np.allclose(np.linalg.norm(E, axis=1), 1.0, atol=1e-3)
    # semantically: revert~undo closer than revert~bread
    assert (E[0] @ E[1]) > (E[0] @ E[2])

def test_embed_empty_list():
    E = embed_texts([])
    assert E.shape == (0, 384)
