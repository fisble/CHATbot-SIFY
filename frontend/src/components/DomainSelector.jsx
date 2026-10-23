/**
 * Domain selector component for choosing storyboard domain.
 */

import { useSelector, useDispatch } from 'react-redux';
import {
  selectSelectedDomain,
  selectAvailableDomains,
  setSelectedDomain,
} from '../store/querySlice';
import { selectStatus } from '../store/agentSlice';

/**
 * Domain display names and descriptions.
 */
const DOMAIN_INFO = {
  product_demo: {
    name: 'Product Demo',
    description: 'Tech product showcases and feature demonstrations',
    icon: '📱',
  },
  education: {
    name: 'Education',
    description: 'Instructional and learning content',
    icon: '📚',
  },
  medical: {
    name: 'Medical',
    description: 'Healthcare and medical visualizations',
    icon: '🏥',
  },
  marketing: {
    name: 'Marketing',
    description: 'Brand and promotional content',
    icon: '📣',
  },
  film_style: {
    name: 'Film Style',
    description: 'Cinematic storytelling',
    icon: '🎬',
  },
  gaming: {
    name: 'Gaming',
    description: 'Game trailers and interactive content',
    icon: '🎮',
  },
};

/**
 * DomainSelector component.
 */
function DomainSelector() {
  const dispatch = useDispatch();
  const selectedDomain = useSelector(selectSelectedDomain);
  const availableDomains = useSelector(selectAvailableDomains);
  const status = useSelector(selectStatus);
  
  const isDisabled = status === 'running' || status === 'connecting';
  
  const handleDomainChange = (domain) => {
    if (!isDisabled) {
      dispatch(setSelectedDomain(domain));
    }
  };
  
  return (
    <div className="domain-selector">
      <h3 className="section-title">Select Domain</h3>
      <div className="domain-grid">
        {availableDomains.map((domain) => {
          const info = DOMAIN_INFO[domain] || {
            name: domain,
            description: 'Custom domain',
            icon: '📋',
          };
          
          return (
            <button
              key={domain}
              className={`domain-card ${selectedDomain === domain ? 'selected' : ''} ${isDisabled ? 'disabled' : ''}`}
              onClick={() => handleDomainChange(domain)}
              disabled={isDisabled}
            >
              <span className="domain-icon">{info.icon}</span>
              <span className="domain-name">{info.name}</span>
              <span className="domain-description">{info.description}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default DomainSelector;

