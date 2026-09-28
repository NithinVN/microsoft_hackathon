import React, { useState } from 'react';
import { PostmortemData } from '../types/incident';
import { Sparkles, CheckCircle2, Star, Clock, Brain, FileCheck, Send, ShieldCheck } from 'lucide-react';

interface PostmortemLearningLoopProps {
  postmortem: PostmortemData;
  onRetainToHindsight: (feedback: string, rating: number) => void;
  isRetaining: boolean;
}

export const PostmortemLearningLoop: React.FC<PostmortemLearningLoopProps> = ({
  postmortem,
  onRetainToHindsight,
  isRetaining,
}) => {
  const [rating, setRating] = useState<number>(postmortem.engineerRating || 5);
  const [feedback, setFeedback] = useState<string>(
    postmortem.engineerFeedback ||
      'The Hindsight Failed-Fix warning prevented an accidental reboot disaster. Pool scaling and idle connection kill resolved the issue cleanly.'
  );

  return (
    <div className="card postmortem-card">
      <div className="card-header flex-row">
        <div className="flex-row items-center gap-2">
          <Brain size={20} className="text-purple" />
          <div>
            <h3 className="card-title">Continuous Learning Loop: Incident Postmortem & Feedback</h3>
            <span className="text-xs text-muted">
              Incident Outcome → Postmortem → Engineer Review → Hindsight Retain → Smarter Future Response
            </span>
          </div>
        </div>

        {postmortem.retainedToHindsight ? (
          <div className="retained-badge">
            <CheckCircle2 size={16} className="text-green" />
            <span>Retained in Hindsight Memory ({postmortem.hindsightMemoryId})</span>
          </div>
        ) : (
          <div className="pending-retention-badge">
            <Sparkles size={14} className="text-purple" />
            <span>Pending Hindsight Memory Retain</span>
          </div>
        )}
      </div>

      <div className="card-body">
        <div className="grid-two-col">
          {/* Postmortem Details */}
          <div className="postmortem-col">
            <h4 className="section-title">
              <FileCheck size={16} className="text-blue inline-icon" /> Automated Postmortem Summary
            </h4>

            <div className="pm-field-box">
              <span className="pm-label">INCIDENT TITLE:</span>
              <p className="pm-value">{postmortem.title}</p>
            </div>

            <div className="pm-meta-row">
              <div>
                <span className="pm-label">TOTAL DURATION:</span>
                <span className="pm-value">{postmortem.durationMinutes} minutes</span>
              </div>
              <div>
                <span className="pm-label">SEVERITY:</span>
                <span className="pm-value text-red">{postmortem.severity}</span>
              </div>
              <div>
                <span className="pm-label">DETECTION SOURCE:</span>
                <span className="pm-value">{postmortem.detectionSource}</span>
              </div>
            </div>

            <div className="pm-field-box mt-3">
              <span className="pm-label">ROOT CAUSE DETERMINATION:</span>
              <p className="pm-value text-secondary">{postmortem.rootCause}</p>
            </div>

            <div className="pm-field-box mt-3">
              <span className="pm-label">CORRECTIVE ACTIONS & JIRA TASKS:</span>
              <ul className="pm-action-list">
                {postmortem.correctiveActions.map((action, aidx) => (
                  <li key={aidx}>
                    <CheckCircle2 size={14} className="text-green inline-icon" />
                    <span>{action}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Timeline & Feedback */}
          <div className="postmortem-col">
            <h4 className="section-title">
              <Clock size={16} className="text-cyan inline-icon" /> Chronological Timeline
            </h4>
            <div className="timeline-flow">
              {postmortem.timeline.map((event, eidx) => (
                <div key={eidx} className="timeline-node">
                  <span className="time-tag">{event.time}</span>
                  <div className="timeline-dot"></div>
                  <span className="time-text">{event.event}</span>
                </div>
              ))}
            </div>

            {/* Engineer Feedback Form */}
            <div className="engineer-feedback-card mt-4">
              <h4 className="feedback-title">
                <Sparkles size={16} className="text-purple inline-icon" /> Engineer Evaluation & Memory Retain
              </h4>
              <p className="feedback-subtitle">
                Provide feedback to train Hindsight Cloud organizational memory on the effectiveness of this remediation.
              </p>

              <div className="rating-row mt-2">
                <span className="rating-label">Remediation Efficacy Rating:</span>
                <div className="stars-container">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <button
                      key={star}
                      className={`star-btn ${rating >= star ? 'star-filled' : ''}`}
                      onClick={() => setRating(star)}
                    >
                      <Star size={18} fill={rating >= star ? '#fbbf24' : 'none'} />
                    </button>
                  ))}
                  <span className="star-text">{rating} / 5 Stars</span>
                </div>
              </div>

              <div className="feedback-input-box mt-3">
                <label className="text-xs text-muted block mb-1">
                  Postmortem Feedback & Institutional Lessons Learned:
                </label>
                <textarea
                  className="form-textarea"
                  rows={3}
                  value={feedback}
                  onChange={(e) => setFeedback(e.target.value)}
                  placeholder="Record insights or nuances for future engineers..."
                />
              </div>

              <button
                className={`btn-retain-hindsight mt-3 ${postmortem.retainedToHindsight ? 'btn-retained' : ''}`}
                disabled={isRetaining || postmortem.retainedToHindsight}
                onClick={() => onRetainToHindsight(feedback, rating)}
              >
                {postmortem.retainedToHindsight ? (
                  <>
                    <ShieldCheck size={16} />
                    <span>Memory Retained in Hindsight Cloud Store</span>
                  </>
                ) : isRetaining ? (
                  <>
                    <span className="spin">⟳</span>
                    <span>Updating Hindsight Memory...</span>
                  </>
                ) : (
                  <>
                    <Send size={16} />
                    <span>Retain to Hindsight Organizational Memory</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
