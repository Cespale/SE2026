import React from 'react';
import { useAuthStore } from '../../stores/authStore';

const LoginModal = React.lazy(() => import('./LoginModal').then(({ LoginModal }) => ({ default: LoginModal })));
const RegisterModal = React.lazy(() => import('./RegisterModal').then(({ RegisterModal }) => ({ default: RegisterModal })));

export function AuthModals() {
  const {
    showLoginModal,
    showRegisterModal,
    closeLoginModal,
    closeRegisterModal,
    openRegisterModal,
    openLoginModal,
  } = useAuthStore();

  return (
    <>
      {showLoginModal && (
        <React.Suspense fallback={null}>
          <LoginModal
            onClose={closeLoginModal}
            onRegister={openRegisterModal}
          />
        </React.Suspense>
      )}

      {showRegisterModal && (
        <React.Suspense fallback={null}>
          <RegisterModal
            onClose={closeRegisterModal}
            onLogin={openLoginModal}
          />
        </React.Suspense>
      )}
    </>
  );
}
