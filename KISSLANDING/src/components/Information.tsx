import React, { useEffect, useRef } from 'react';
import { LocationIcon, CalendarIcon, ClockIcon, MusicIcon, ChatIcon } from './Icons';
import './Information.css';

declare global {
  interface Window {
    ymaps: any;
  }
}

const Information: React.FC = () => {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);

  useEffect(() => {
    if (!window.ymaps || !mapRef.current) return;

    window.ymaps.ready(() => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.destroy();
      }

      mapInstanceRef.current = new window.ymaps.Map(mapRef.current, {
        center: [48.468892, 135.063239],
        zoom: 16,
        controls: ['zoomControl', 'trafficControl']
      });

      const placemark = new window.ymaps.Placemark(
        [48.468892, 135.063239],
        {
          balloonContent: 'Клуб Loona<br>ул. Тургенева 46, г. Хабаровск'
        },
        {
          preset: 'islands#redIcon'
        }
      );

      mapInstanceRef.current.geoObjects.add(placemark);
    });

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.destroy();
      }
    };
  }, []);

  return (
    <section className="information-section">
      <div className="information-header">
        <div className="information-title-container">
          <StarIcon />
          <h2 className="information-title">ИНФОРМАЦИЯ</h2>
          <StarIcon />
        </div>
        <p className="information-subtitle">Вся необходимая информация о мероприятии</p>
      </div>
      
      <div className="information-content">
        <div className="information-panel">
          <div className="info-grid">
            <div className="info-item">
              <div className="info-header">
                <LocationIcon className="info-icon" />
                <h3 className="info-title">Место проведения</h3>
              </div>
              <p className="info-value">Клуб Loona</p>
            </div>

            <div className="info-item">
              <div className="info-header">
                <LocationIcon className="info-icon" />
                <h3 className="info-label">Адрес</h3>
              </div>
              <p className="info-text">ул. Тургенева 46</p>
              <p className="info-text">г. Хабаровск</p>
            </div>

            <div className="info-item">
              <div className="info-header">
                <CalendarIcon className="info-icon" />
                <h3 className="info-label">Дата</h3>
              </div>
              <p className="info-value">Скоро</p>
            </div>

            <div className="info-item">
              <div className="info-header">
                <ClockIcon className="info-icon" />
                <h3 className="info-label">Время</h3>
              </div>
              <p className="info-value">Уточняется</p>
            </div>
          </div>

          <div className="info-item info-item-full">
            <div className="info-header">
              <MusicIcon className="info-icon" />
              <h3 className="info-label">О клубе</h3>
            </div>
            <p className="info-description">
              Loona — одно из самых популярных мест для тусовок в Хабаровске. 
              Современное звуковое оборудование, стильный интерьер и незабываемая 
              атмосфера ждут тебя на нашей вечеринке!
            </p>
          </div>

          <div className="map-container">
            <div ref={mapRef} className="yandex-map"></div>
            <a 
              href="https://yandex.ru/maps/?pt=135.063239,48.468892&z=16"
              target="_blank"
              rel="noopener noreferrer"
              className="map-link"
              aria-label="Открыть адрес клуба Loona в Яндекс Картах"
            >
              <LocationIcon className="map-link-icon" />
              <span>Открыть в Яндекс Картах</span>
            </a>
          </div>

          <a 
            href="https://t.me/kissparty_chat" 
            target="_blank" 
            rel="noopener noreferrer"
            className="chat-button"
            aria-label="Перейти в Telegram чат KISS PARTY"
          >
            <ChatIcon className="chat-icon" />
            <span>Чат для общения</span>
          </a>
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

export default Information;

