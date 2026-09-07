"use client";

import { createContext,useCallback,useContext,useEffect,useMemo,useState } from "react";
import { enumLabel as displayEnum,Locale,messages,TranslationKey } from "./messages";

const STORAGE_KEY="ai-business-radar.locale";
type I18nValue={locale:Locale;setLocale:(locale:Locale)=>void;t:(key:TranslationKey)=>string;enumLabel:(value:string)=>string};
const defaultValue:I18nValue={locale:"zh-CN",setLocale:()=>undefined,t:key=>messages["zh-CN"][key],enumLabel:value=>displayEnum("zh-CN",value)};
const I18nContext=createContext<I18nValue>(defaultValue);

export function LocaleProvider({children}:{children:React.ReactNode}){
  const [locale,setLocaleState]=useState<Locale>("zh-CN");
  useEffect(()=>{const saved=window.localStorage.getItem(STORAGE_KEY);if(saved==="zh-CN"||saved==="en-US"){const timer=window.setTimeout(()=>setLocaleState(saved),0);return()=>window.clearTimeout(timer)}},[]);
  const setLocale=useCallback((next:Locale)=>{setLocaleState(next);window.localStorage.setItem(STORAGE_KEY,next);document.documentElement.lang=next},[]);
  useEffect(()=>{document.documentElement.lang=locale},[locale]);
  const value=useMemo<I18nValue>(()=>({locale,setLocale,t:key=>messages[locale][key],enumLabel:value=>displayEnum(locale,value)}),[locale,setLocale]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(){return useContext(I18nContext)}
