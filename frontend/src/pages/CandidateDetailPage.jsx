import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { candidatesAPI } from '../api/client';

export default function CandidateDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [candidate, setCandidate] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Scoring form state
  const [scoreCategory, setScoreCategory] = useState('Technical Skills');
  const [scoreValue, setScoreValue] = useState(3);
  const [scoreNote, setScoreNote] = useState('');
  const [submittingScore, setSubmittingScore] = useState(false);
  const [scoreSuccess, setScoreSuccess] = useState('');

  // AI summary state
  const [generatingSummary, setGeneratingSummary] = useState(false);
  const [summaryError, setSummaryError] = useState('');

  // Internal notes state (admin only)
  const [notes, setNotes] = useState('');
  const [savingNotes, setSavingNotes] = useState(false);
  const [notesSuccess, setNotesSuccess] = useState('');

  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const isAdmin = user.role === 'admin';

  const categories = [
    'Technical Skills',
    'Communication',
    'Problem Solving',
    'Cultural Fit',
    'Leadership',
    'Domain Knowledge',
  ];

  const fetchCandidate = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await candidatesAPI.getById(id);
      setCandidate(response.data);
      if (response.data.internal_notes !== undefined) {
        setNotes(response.data.internal_notes || '');
      }
    } catch (err) {
      setError('Failed to load candidate details.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCandidate();
  }, [id]);

  const handleSubmitScore = async (e) => {
    e.preventDefault();
    setSubmittingScore(true);
    setScoreSuccess('');
    try {
      await candidatesAPI.submitScore(id, {
        category: scoreCategory,
        score: scoreValue,
        note: scoreNote,
      });
      setScoreSuccess('Score submitted successfully!');
      setScoreNote('');
      setScoreValue(3);
      fetchCandidate(); // Refresh to show new score
      setTimeout(() => setScoreSuccess(''), 3000);
    } catch (err) {
      setError('Failed to submit score.');
    } finally {
      setSubmittingScore(false);
    }
  };

  const handleGenerateSummary = async () => {
    setGeneratingSummary(true);
    setSummaryError('');
    try {
      const response = await candidatesAPI.generateSummary(id);
      setCandidate((prev) => ({ ...prev, ai_summary: response.data.summary }));
    } catch (err) {
      setSummaryError('Failed to generate AI summary. Please try again.');
    } finally {
      setGeneratingSummary(false);
    }
  };

  const handleSaveNotes = async () => {
    setSavingNotes(true);
    setNotesSuccess('');
    try {
      await candidatesAPI.updateNotes(id, notes);
      setNotesSuccess('Notes saved!');
      setTimeout(() => setNotesSuccess(''), 3000);
    } catch (err) {
      setError('Failed to save notes.');
    } finally {
      setSavingNotes(false);
    }
  };

  const getStatusColor = (status) => {
    const colors = {
      new: 'status-new',
      reviewed: 'status-reviewed',
      hired: 'status-hired',
      rejected: 'status-rejected',
      archived: 'status-archived',
    };
    return colors[status] || '';
  };

  if (loading) {
    return (
      <div className="detail-page">
        <div className="loading-state">
          <div className="spinner large"></div>
          <p>Loading candidate details...</p>
        </div>
      </div>
    );
  }

  if (error && !candidate) {
    return (
      <div className="detail-page">
        <div className="error-message">{error}</div>
        <button className="btn btn-primary" onClick={() => navigate('/')}>Back to List</button>
      </div>
    );
  }

  if (!candidate) return null;

  return (
    <div className="detail-page">
      {/* Back Navigation */}
      <nav className="detail-nav">
        <button className="btn btn-ghost" onClick={() => navigate('/')}>
          ← Back to Candidates
        </button>
      </nav>

      {/* Profile Header */}
      <section className="profile-header">
        <div className="profile-avatar large">
          {candidate.name.split(' ').map(n => n[0]).join('').slice(0, 2)}
        </div>
        <div className="profile-info">
          <h1>{candidate.name}</h1>
          <p className="profile-email">{candidate.email}</p>
          <p className="profile-role">{candidate.role_applied}</p>
          <div className="profile-meta">
            <span className={`status-badge ${getStatusColor(candidate.status)}`}>
              {candidate.status}
            </span>
            <span className="meta-date">Applied {new Date(candidate.created_at).toLocaleDateString()}</span>
          </div>
          <div className="skills-list">
            {candidate.skills.map((skill) => (
              <span key={skill} className="skill-tag">{skill}</span>
            ))}
          </div>
        </div>
      </section>

      {error && <div className="error-message">{error}</div>}

      <div className="detail-grid">
        {/* Scores Section */}
        <section className="detail-section">
          <h2>
            Scores
            {isAdmin && <span className="section-note">(All reviewers)</span>}
            {!isAdmin && <span className="section-note">(Your scores only)</span>}
          </h2>
          
          {candidate.scores && candidate.scores.length > 0 ? (
            <div className="scores-list">
              {candidate.scores.map((score) => (
                <div key={score.id} className="score-item">
                  <div className="score-header">
                    <span className="score-category">{score.category}</span>
                    <div className="score-stars">
                      {[1, 2, 3, 4, 5].map((star) => (
                        <span key={star} className={`star ${star <= score.score ? 'filled' : ''}`}>★</span>
                      ))}
                    </div>
                  </div>
                  {score.note && <p className="score-note">{score.note}</p>}
                  <div className="score-meta">
                    {isAdmin && <span className="reviewer-name">by {score.reviewer_name}</span>}
                    <span className="score-date">{new Date(score.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="empty-text">No scores yet.</p>
          )}
        </section>

        {/* Scoring Form */}
        <section className="detail-section">
          <h2>Submit Score</h2>
          <form onSubmit={handleSubmitScore} className="score-form">
            <div className="form-group">
              <label htmlFor="score-category">Category</label>
              <select
                id="score-category"
                value={scoreCategory}
                onChange={(e) => setScoreCategory(e.target.value)}
              >
                {categories.map((cat) => (
                  <option key={cat} value={cat}>{cat}</option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label>Score</label>
              <div className="score-selector">
                {[1, 2, 3, 4, 5].map((val) => (
                  <button
                    key={val}
                    type="button"
                    className={`score-btn ${scoreValue === val ? 'active' : ''}`}
                    onClick={() => setScoreValue(val)}
                  >
                    {val}
                  </button>
                ))}
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="score-note">Note (optional)</label>
              <textarea
                id="score-note"
                value={scoreNote}
                onChange={(e) => setScoreNote(e.target.value)}
                placeholder="Add a note about this score..."
                rows={3}
              />
            </div>

            {scoreSuccess && <div className="success-message">{scoreSuccess}</div>}

            <button type="submit" className="btn btn-primary" disabled={submittingScore}>
              {submittingScore ? (
                <span className="loading-spinner"><span className="spinner"></span> Submitting...</span>
              ) : 'Submit Score'}
            </button>
          </form>
        </section>

        {/* AI Summary Section */}
        <section className="detail-section ai-section">
          <h2>AI Summary</h2>
          
          {candidate.ai_summary ? (
            <div className="ai-summary-content">
              {candidate.ai_summary.split('\n').map((line, i) => (
                <p key={i}>{line}</p>
              ))}
            </div>
          ) : (
            <p className="empty-text">No AI summary generated yet.</p>
          )}

          {summaryError && <div className="error-message">{summaryError}</div>}

          <button
            className="btn btn-secondary"
            onClick={handleGenerateSummary}
            disabled={generatingSummary}
          >
            {generatingSummary ? (
              <span className="loading-spinner">
                <span className="spinner"></span>
                Generating summary... (this takes a moment)
              </span>
            ) : (
              candidate.ai_summary ? '🔄 Regenerate AI Summary' : '✨ Generate AI Summary'
            )}
          </button>
        </section>

        {/* Admin-only Internal Notes */}
        {isAdmin && (
          <section className="detail-section admin-section">
            <h2>
              🔒 Internal Notes
              <span className="section-note">(Admin only)</span>
            </h2>
            <textarea
              id="internal-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Add confidential notes about this candidate..."
              rows={4}
              className="notes-textarea"
            />
            {notesSuccess && <div className="success-message">{notesSuccess}</div>}
            <button
              className="btn btn-primary"
              onClick={handleSaveNotes}
              disabled={savingNotes}
            >
              {savingNotes ? (
                <span className="loading-spinner"><span className="spinner"></span> Saving...</span>
              ) : 'Save Notes'}
            </button>
          </section>
        )}
      </div>
    </div>
  );
}
