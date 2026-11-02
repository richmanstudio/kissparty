import React from 'react';
import { QRIcon, ArrowRightIcon, TicketIcon } from './Icons';
import './Tickets.css';

const Tickets: React.FC = () => {
  return (
    <section className="tickets-section">
      <div className="tickets-container">
        <div className="tickets-header">
          <div className="tickets-title-container">
            <StarIcon />
            <h2 className="tickets-title">ПОКУПКА БИЛЕТОВ</h2>
            <StarIcon />
          </div>
          <p className="tickets-subtitle">
            Приобрети билет прямо сейчас через нашего Telegram бота
          </p>
          <div className="tickets-underline"></div>
        </div>

        <div className="tickets-content">
          <div className="qr-section">
            <div className="qr-container">
              <img 
                src="/media/qr-code.png" 
                alt="QR код для перехода в Telegram бот KISS PARTY PAY" 
                className="qr-code"
                loading="lazy"
                width="400"
                height="400"
              />
            </div>
            <p className="qr-caption">
              <QRIcon className="qr-icon" />
              Отсканируй QR код для перехода в бота
            </p>
          </div>

          <div className="features-section">
            <div className="feature-card">
              <div className="feature-icon-container">
                <TicketIcon className="feature-icon" />
              </div>
              <h3 className="feature-title">Быстрая покупка</h3>
              <p className="feature-description">
                Наш Telegram бот поможет тебе быстро и удобно приобрести билет на тусовку
              </p>
            </div>

            <div className="feature-card">
              <div className="feature-icon-container">
                <QRIcon className="feature-icon" />
              </div>
              <h3 className="feature-title">Просто и удобно</h3>
              <p className="feature-description">
                Отсканируй QR код или перейди по ссылке, чтобы начать покупку
              </p>
            </div>

            <a 
              href="https://t.me/kisspartypay_bot"
              target="_blank"
              rel="noopener noreferrer"
              className="ticket-button"
              aria-label="Перейти к покупке билета в Telegram боте KISS PARTY PAY"
            >
              <span>Перейти к покупке билета</span>
              <ArrowRightIcon className="button-arrow" />
            </a>
          </div>
        </div>
      </div>
    </section>
  );
};

const StarIcon: React.FC = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" fill="#C0C0C0"/>
  </svg>
);

export default Tickets;

