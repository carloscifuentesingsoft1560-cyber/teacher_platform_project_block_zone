import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { ProveedorAutenticacion } from './autenticacion/ContextoAutenticacion.jsx';
import { Aplicacion } from './Aplicacion.jsx';
import './estilos/principal.scss';

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <ProveedorAutenticacion><Aplicacion /></ProveedorAutenticacion>
    </BrowserRouter>
  </React.StrictMode>,
);
