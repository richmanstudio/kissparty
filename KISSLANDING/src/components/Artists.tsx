import React from 'react';
import { Swiper, SwiperSlide } from 'swiper/react';
import { Navigation, Pagination, Autoplay } from 'swiper/modules';
import { TelegramIcon, InstagramIcon, VKIcon } from './Icons';
import 'swiper/css';
import 'swiper/css/navigation';
import 'swiper/css/pagination';
import './Artists.css';

interface Artist {
  id: string;
  name: string;
  image: string;
  socialLinks: {
    telegram?: string;
    instagram?: string;
    vk?: string;
  };
}

const artists: Artist[] = [
  {
    id: 'lilfoam',
    name: 'Lil Foam',
    image: '/media/lilfoam.webp',
    socialLinks: {
      telegram: 'https://t.me/lilfoamtg',
      instagram: 'https://www.instagram.com/lil4am?igsh=OHV5Z3dxNWtuMnk1',
    }
  },
  {
    id: 'prettykiss',
    name: 'Pretty Kiss',
    image: '/media/prettykiss.webp',
    socialLinks: {
      telegram: 'https://t.me/imprettykiss',
      instagram: 'https://www.instagram.com/imprettykiss?igsh=cjBxb2l2NDNrdmc0',
    }
  },
  {
    id: 'stickid',
    name: 'Stickid',
    image: '/media/stickid.webp',
    socialLinks: {
      telegram: 'https://t.me/stickidd',
      instagram: 'https://www.instagram.com/_stickid_?igsh=eTVsaW5jMTRnczU1',
    }
  }
];

const Artists: React.FC = () => {
  return (
    <section className="artists-section">
      <div className="artists-container">
        <div className="artists-header">
          <h2 className="artists-title">АРТИСТЫ</h2>
          <p className="artists-subtitle">Наши звезды вечеринки</p>
        </div>
        <Swiper
          modules={[Navigation, Pagination, Autoplay]}
          spaceBetween={50}
          slidesPerView={1}
          navigation
          pagination={{ clickable: true }}
          autoplay={{
            delay: 5000,
            disableOnInteraction: false,
          }}
          loop={true}
          className="artists-swiper"
        >
          {artists.map((artist) => (
            <SwiperSlide key={artist.id}>
              <div className="artist-card">
                <div className="artist-image-container">
                  <img 
                    src={artist.image} 
                    alt={`${artist.name} - артист KISS PARTY`}
                    className="artist-image"
                    loading="lazy"
                    width="600"
                    height="600"
                    onError={(e) => {
                      const target = e.target as HTMLImageElement;
                      target.src = artist.image.replace('.webp', '.png');
                    }}
                  />
                </div>
                <div className="artist-info">
                  <h2 className="artist-name">{artist.name}</h2>
                  <div className="artist-social">
                    {artist.socialLinks.telegram && (
                      <a 
                        href={artist.socialLinks.telegram} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="social-link"
                        aria-label="Telegram"
                      >
                        <TelegramIcon />
                      </a>
                    )}
                    {artist.socialLinks.instagram && (
                      <a 
                        href={artist.socialLinks.instagram} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="social-link"
                        aria-label="Instagram"
                      >
                        <InstagramIcon />
                      </a>
                    )}
                    {artist.socialLinks.vk && (
                      <a 
                        href={artist.socialLinks.vk} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="social-link"
                        aria-label="VK"
                      >
                        <VKIcon />
                      </a>
                    )}
                  </div>
                </div>
              </div>
            </SwiperSlide>
          ))}
        </Swiper>
      </div>
    </section>
  );
};

export default Artists;

